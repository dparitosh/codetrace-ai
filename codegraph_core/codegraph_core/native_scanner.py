"""C-family syntax facts. Never executes builds, preprocessors or source code.

Tree-sitter provides syntax, not compiler binding. Only unique lexical call targets
are linked; receivers, ambiguous overloads and macro/build configuration stay unknown.
"""
import importlib
import re
from functools import lru_cache
from pathlib import PurePosixPath

LANGUAGES = {'.c': 'c', '.h': 'cpp', '.cc': 'cpp', '.cpp': 'cpp', '.cxx': 'cpp',
             '.c++': 'cpp', '.hpp': 'cpp', '.hh': 'cpp', '.hxx': 'cpp', '.ipp': 'cpp',
             '.inl': 'cpp', '.tpp': 'cpp', '.ixx': 'cpp', '.cs': 'csharp'}
GRAMMARS = {'c': 'tree_sitter_c', 'cpp': 'tree_sitter_cpp', 'csharp': 'tree_sitter_c_sharp'}
TYPES = {'class_specifier', 'struct_specifier', 'union_specifier', 'enum_specifier',
         'class_declaration', 'struct_declaration', 'interface_declaration', 'enum_declaration', 'record_declaration'}
CALLABLES = {'method_declaration', 'constructor_declaration', 'destructor_declaration', 'local_function_statement'}


@lru_cache(maxsize=3)
def grammar(language):
    from tree_sitter import Language
    return Language(importlib.import_module(GRAMMARS[language]).language())


def text(node):
    return node.text.decode('utf-8', errors='replace') if node is not None else ''


def qualified(value):
    return value.replace('::', '.').replace('global.', '').strip('.')


def declarator(node):
    while node is not None and node.type != 'function_declarator':
        node = node.child_by_field_name('declarator')
    return node


def identifier(node):
    while node is not None:
        if node.type in {'identifier', 'field_identifier', 'type_identifier'}:
            return text(node)
        node = node.child_by_field_name('declarator') or node.child_by_field_name('name')
    return ''


def parameter_type(parameter):
    """Keep declarator shape (arrays/references/pointers), excluding its name."""
    modifiers = ' '.join(text(c) for c in parameter.named_children if c.type in {'modifier', 'type_qualifier'})
    value = parameter.child_by_field_name('declarator')
    name = value
    while name is not None and name.type not in {'identifier', 'field_identifier'}:
        name = name.child_by_field_name('declarator')
    shape = value.text if value is not None else b''
    if name is not None:
        start, end = name.start_byte - value.start_byte, name.end_byte - value.start_byte
        shape = shape[:start] + shape[end:]
    return ' '.join(re.findall(r'\w+|[^\w\s]', modifiers + ' ' + text(parameter.child_by_field_name('type')) + shape.decode('utf-8')))


def scan_native(graph, path, source, file_id):
    """Return False when optional grammars are absent; caller reports fallback."""
    language = LANGUAGES[path.suffix.lower()]
    try:
        from tree_sitter import Parser
        parser = Parser(grammar(language))
    except (ImportError, ValueError):
        graph.g.nodes[file_id].attrs.update(language=language, parser_warning='Tree-sitter runtime/grammar unavailable or incompatible; install backend/requirements-local.txt')
        return False
    tree = parser.parse(source.encode('utf-8'))
    root = tree.root_node
    if path.suffix.lower() == '.h':
        # Prefer C for C-compatible headers; C++ constructs select the C++ grammar.
        from tree_sitter import Parser
        try:
            c_tree = Parser(grammar('c')).parse(source.encode('utf-8'))
        except (ImportError, ValueError):
            c_tree = None
        if c_tree is not None and not c_tree.root_node.has_error:
            language, tree, root = 'c', c_tree, c_tree.root_node
    graph.g.nodes[file_id].attrs.update(language=language, extraction='tree_sitter',
        parse_status='partial' if root.has_error else 'parsed', syntax_errors=root.has_error)
    module = graph._module_id(path)
    filename = path.as_posix()
    graph.g.upsert_node(module, 'module', name=path.stem, path=filename, language=language, extraction='tree_sitter')
    graph.g.add_edge(file_id, module, 'defines')
    file_namespace = next((qualified(text(n.child_by_field_name('name'))) for n in root.named_children
                           if n.type == 'file_scoped_namespace_declaration'), '')

    def add(kind, name, node, owner, scope, **props):
        full = '.'.join(part for part in (scope, qualified(name)) if part)
        key = f'{kind}:{filename}::{full}'
        if kind == 'function':
            if props.get('generic_arity'):
                key += f"<{props['generic_arity']}>"
            key += '(' + ','.join(props.get('parameter_types', [])) + ')' + props.get('qualifiers', '')
        elif kind == 'variable':
            key += f'@{node.start_point.row + 1}:{owner}'
        old = graph.g.nodes.get(key)
        if not old or not old.attrs.get('has_body'):
            graph.g.upsert_node(key, kind, name=name.split('::')[-1], qualified_name=full,
                path=filename, start=node.start_point.row + 1, end=node.end_point.row + 1,
                language=language, extraction='tree_sitter', owner=owner, scope=scope, **props)
        if not old:
            graph._native_pending.append({'kind': 'owns', 'source': owner, 'target': key})
        return key, full

    def walk(node, owner=module, scope=file_namespace, function=None, selected_declarator=None):
        if node.type in {'comment', 'string_literal', 'raw_string_literal', 'verbatim_string_literal', 'interpolated_string_expression', 'character_literal'}:
            return
        if node.type in {'lambda_expression', 'anonymous_method_expression'}:
            # These have their own execution scope. Do not attribute their deferred
            # calls to the containing named function without delegate/closure binding.
            return
        if node.type == 'preproc_include':
            target = text(node.child_by_field_name('path'))
            if target.startswith(('"', '<')):
                graph._native_pending.append({'kind': 'import', 'source': module, 'name': target[1:-1], 'path': filename,
                    'local': target.startswith('"'), 'language': language, 'line': node.start_point.row + 1})
            return
        if node.type == 'using_directive':
            graph._native_pending.append({'kind': 'using', 'source': module,
                'name': text(node).removeprefix('using ').removesuffix(';').strip(), 'language': language, 'path': filename})
            return
        if node.type in {'namespace_definition', 'namespace_declaration'}:
            name = text(node.child_by_field_name('name')) or '(anonymous)'
            child_owner, child_scope = add('package', name, node, owner, scope, classification='namespace')
            body = node.child_by_field_name('body')
            if body is not None:
                for child in body.named_children:
                    walk(child, child_owner, child_scope)
            return
        if node.type in TYPES:
            name = text(node.child_by_field_name('name')) or f'(anonymous@{node.start_point.row + 1})'
            child_owner, child_scope = add('class', name, node, owner, scope, declaration_kind=node.type)
            for child in node.named_children:
                if child.type in {'base_list', 'base_class_clause'}:
                    for base in child.named_children:
                        if base.type not in {'access_specifier', 'virtual'}:
                            graph._native_pending.append({'kind': 'inherits_from', 'source': child_owner,
                                'name': qualified(text(base)), 'scope': scope, 'path': filename, 'language': language})
            body = node.child_by_field_name('body')
            if body is not None:
                for child in body.named_children:
                    walk(child, child_owner, child_scope)
            return
        if node.type in {'declaration', 'field_declaration'} and selected_declarator is None:
            declarations = node.children_by_field_name('declarator')
            if len(declarations) > 1:
                for value in declarations:
                    walk(node, owner, scope, function, value)
                return
        decl = declarator(selected_declarator or node.child_by_field_name('declarator')) if node.type in {'function_definition', 'declaration', 'field_declaration'} else None
        native_callable = node.type in CALLABLES or (decl is not None and
            decl.child_by_field_name('declarator') is not None and
            decl.child_by_field_name('declarator').type in {'identifier', 'field_identifier', 'qualified_identifier', 'destructor_name', 'operator_name'})
        if native_callable:
            name = text(node.child_by_field_name('name')) if node.type in CALLABLES else text(decl.child_by_field_name('declarator'))
            parameters = node.child_by_field_name('parameters') if node.type in CALLABLES else decl.child_by_field_name('parameters')
            params = [p for p in (parameters.named_children if parameters is not None else [])
                      if p.type in {'parameter', 'parameter_declaration', 'optional_parameter_declaration', 'variadic_parameter'}]
            types = [parameter_type(p) for p in params]
            if language != 'csharp' and len(types) == 1 and types[0] == 'void':
                params, types = [], []
            body = node.child_by_field_name('body')
            # Qualified out-of-class definitions retain their explicit lexical owner.
            name_parts = qualified(name).split('.')
            explicit_scope = '.'.join(name_parts[:-1])
            owner_scope = (explicit_scope if not scope or explicit_scope == scope or explicit_scope.startswith(scope + '.')
                           else scope + '.' + explicit_scope) if len(name_parts) > 1 else scope
            function_id, full = add('function', name_parts[-1], node, owner, owner_scope,
                parameter_types=types, parameter_count=len(params), has_body=body is not None,
                generic_arity=sum(len(c.named_children) for c in node.named_children if c.type == 'type_parameter_list'),
                qualifiers=' '.join(text(c) for c in decl.named_children if c.type in {'type_qualifier', 'ref_qualifier'}) if decl is not None else '',
                internal_linkage=language != 'csharp' and bool(re.search(r'\bstatic\b', text(node)[:max(0, (body.start_byte - node.start_byte) if body else len(text(node)))])))
            for param in params:
                param_name = text(param.child_by_field_name('name')) or identifier(param.child_by_field_name('declarator'))
                if param_name:
                    add('variable', param_name, param, function_id, full, classification='parameter')
            if body is not None:
                walk(body, function_id, full, function_id)
            return
        if node.type in {'call_expression', 'invocation_expression'} and function:
            target = node.child_by_field_name('function')
            name = qualified(text(target))
            call_scope = scope
            member_this = False
            if target is not None and target.type in {'field_expression', 'member_access_expression'}:
                receiver = target.child_by_field_name('argument') or target.child_by_field_name('expression')
                field = target.child_by_field_name('field') or target.child_by_field_name('name')
                name = qualified(text(field)) if text(receiver) == 'this' else name
                member_this = text(receiver) == 'this'
                if member_this:
                    # Explicit this bypasses local functions and parameter bindings.
                    lexical_owner = function
                    while graph.g.nodes[lexical_owner].type == 'function':
                        call_scope = graph.g.nodes[lexical_owner].attrs['scope']
                        lexical_owner = graph.g.nodes[lexical_owner].attrs['owner']
                if text(receiver) != 'this':
                    name = '?' + name  # Receiver type is not established by syntax alone.
            args = node.child_by_field_name('arguments')
            graph._native_pending.append({'kind': 'calls', 'source': function, 'name': name,
                'scope': call_scope, 'path': filename, 'member_this': member_this,
                'absolute': text(target).startswith(('::', 'global::')),
                'language': language, 'arity': len(args.named_children) if args is not None else 0,
                'line': node.start_point.row + 1})
        if node.type == 'variable_declarator':
            name = text(node.child_by_field_name('name'))
            if name:
                add('variable', name, node, owner, scope, classification='local' if function else 'field')
        elif node.type in {'declaration', 'field_declaration'}:
            for value in ([selected_declarator] if selected_declarator is not None else node.children_by_field_name('declarator')):
                name = identifier(value)
                if name:
                    add('variable', name, value, owner, scope, classification='local' if function else 'field')
        elif node.type == 'property_declaration':
            name = text(node.child_by_field_name('name'))
            if name:
                add('variable', name, node, owner, scope, classification='property')
        for child in ([selected_declarator] if selected_declarator is not None else node.named_children):
            walk(child, owner, scope, function)

    try:
        if file_namespace:
            namespace_node = next(n for n in root.named_children if n.type == 'file_scoped_namespace_declaration')
            namespace_id, _ = add('package', file_namespace, namespace_node, module, '', classification='namespace')
            walk(root, namespace_id, file_namespace)
        else:
            walk(root)
    except RecursionError:
        graph.g.nodes[file_id].attrs.update(parse_status='partial',
            parser_warning='Syntax nesting exceeded traversal capacity; extracted structure is partial.')
    return True


def resolve_native(graph):
    """Link only unique lexical identities, leaving unresolved facts explicit."""
    facts = graph._native_pending
    graph._native_pending = []
    symbols = {}
    bindings = {}
    modules = {}
    for key, node in graph.g.nodes.items():
        if node.attrs.get('extraction') != 'tree_sitter':
            continue
        if node.type == 'module':
            modules[node.attrs['path']] = key
        if node.type == 'variable':
            bindings.setdefault(node.attrs['owner'], set()).add(node.attrs['name'])
        if node.type in {'function', 'class', 'package'}:
            symbols.setdefault((node.attrs['language'], node.attrs['qualified_name'], node.type), []).append(key)

    def candidates(fact, kind):
        name, scope = fact['name'], fact.get('scope', '')
        if name.startswith('?'):
            return []
        if kind == 'function' and not fact.get('member_this') and name in bindings.get(fact['source'], set()):
            return []
        scopes = ['' if fact.get('absolute') else scope]
        while scopes[-1]:
            scopes.append(scopes[-1].rsplit('.', 1)[0] if '.' in scopes[-1] else '')
        for prefix in scopes:
            full = '.'.join(filter(None, [prefix, name]))
            found = symbols.get((fact['language'], full, kind), [])
            if kind == 'function':
                found = [key for key in found if not graph.g.nodes[key].attrs.get('internal_linkage') or graph.g.nodes[key].attrs['path'] == fact['path']]
                # Lookup chooses the nearest name before overload compatibility.
                # An incompatible inner declaration still hides outer functions.
                if found:
                    compatible = [key for key in found if graph.g.nodes[key].attrs['parameter_count'] == fact['arity']]
                    if not compatible:
                        return []
                    found = compatible
                definitions = [key for key in found if graph.g.nodes[key].attrs.get('has_body')]
                found = definitions or found
            local = [key for key in found if graph.g.nodes[key].attrs['path'] == fact['path']]
            if local or found:
                return local or found
        return []

    for fact in facts:
        if fact['kind'] == 'owns':
            target = graph.g.nodes[fact['target']]
            owner = fact['source']
            if target.type == 'function' and target.attrs['scope']:
                match = candidates({'name': target.attrs['scope'], 'language': target.attrs['language'],
                                    'path': target.attrs['path']}, 'class')
                if len(match) == 1:
                    owner = match[0]; target.attrs['owner'] = owner
            graph.g.add_edge(owner, fact['target'], 'defines')
            continue
        if fact['kind'] == 'import':
            raw = PurePosixPath(fact['path']).parent / fact['name'].replace('\\', '/')
            # Lexically normalize relative includes without touching the filesystem.
            parts = []
            escaped = False
            for part in raw.parts:
                if part == '..' and parts:
                    parts.pop()
                elif part == '..':
                    escaped = True
                elif part not in {'.', '..'}:
                    parts.append(part)
            paths = ([] if escaped else ['/'.join(parts), fact['name']]) if fact['local'] else [fact['name']]
            matches = [modules[p] for p in paths if p in modules]
            match = matches[:1]
        else:
            match = candidates(fact, 'function' if fact['kind'] == 'calls' else 'class' if fact['kind'] == 'inherits_from' else 'package')
        resolved = len(match) == 1
        if resolved:
            target = match[0]
        else:
            target = f"external:{fact['language']}:{fact['path']}:{fact['name']}"
            graph.g.upsert_node(target, 'external_symbol', name=fact['name'].lstrip('?'),
                language=fact['language'], resolved=False, reason='ambiguous' if len(match) > 1 else 'not_resolved')
        graph.g.add_edge(fact['source'], target, 'imports' if fact['kind'] in {'import', 'using'} else fact['kind'],
                         name=fact['name'].lstrip('?'), start=fact.get('line'), resolved=resolved,
                         resolution='unique_lexical' if resolved else 'unresolved', extraction='tree_sitter')
