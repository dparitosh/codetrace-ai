"""NetworkX software-semantics graph and audit helpers.

The builder accepts semantic records from any parser.  Parsers are deliberately
outside this module: tree-sitter, AST, LSP, or a custom extractor can all emit
the same four-level model.
"""

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

import networkx as nx


LEVELS = ("package", "class", "function", "variable")


class SoftwareArchitectureGraph:
    """Hierarchical, typed software architecture graph."""

    def __init__(self):
        self.graph = nx.MultiDiGraph(name="software-architecture")

    def add_node(self, node_id: str, level: str, name: Optional[str] = None, **attrs: Any) -> str:
        if level not in LEVELS:
            raise ValueError("level must be package, class, function, or variable")
        self.graph.add_node(node_id, level=level, kind=level, name=name or node_id, **attrs)
        return node_id

    def add_relationship(self, source: str, target: str, relationship: str, **attrs: Any) -> None:
        if source not in self.graph or target not in self.graph:
            raise KeyError("both relationship endpoints must be present in the graph")
        # Do not use the relationship name as the key: repeated calls/uses of
        # the same type must remain distinct edges in a MultiDiGraph.
        self.graph.add_edge(source, target, relationship=relationship, **attrs)

    def add_package(self, package: str, **attrs: Any) -> str:
        return self.add_node("package:" + package, "package", package, **attrs)

    def add_class(self, package: str, name: str, **attrs: Any) -> str:
        node_id = "class:" + package + "." + name
        self.add_node(node_id, "class", name, package=package, **attrs)
        self.add_relationship("package:" + package, node_id, "contains")
        return node_id

    def add_function(self, owner: str, name: str, **attrs: Any) -> str:
        level = "class" if owner.startswith("class:") else "package"
        node_id = owner + "::function:" + name
        self.add_node(node_id, "function", name, owner=owner, **attrs)
        self.add_relationship(owner, node_id, "contains")
        return node_id

    def add_variable(self, owner: str, name: str, **attrs: Any) -> str:
        node_id = owner + "::variable:" + name
        self.add_node(node_id, "variable", name, owner=owner, **attrs)
        self.add_relationship(owner, node_id, "contains")
        return node_id

    def add_semantics(self, semantics: Mapping[str, Iterable[Mapping[str, Any]]]) -> None:
        """Load parser output with packages/classes/functions/variables records.

        Each record may include ``id``, ``name``, and arbitrary attributes. Class
        records may include ``package``; function/variable records may include
        ``owner``. Relationships are supplied as ``semantics['relationships']``
        with ``source``, ``target``, and ``relationship`` keys.
        """
        ids: Dict[Tuple[str, str], str] = {}
        for record in semantics.get("packages", []):
            name = str(record.get("name") or record["id"])
            ids[("package", name)] = self.add_package(name, **_attrs(record, "name", "id"))
        for record in semantics.get("classes", []):
            package = str(record.get("package", "default"))
            name = str(record.get("name") or record["id"])
            if "package:" + package not in self.graph:
                self.add_package(package)
            ids[("class", name)] = self.add_class(package, name, **_attrs(record, "name", "id", "package"))
        for record in semantics.get("functions", []):
            owner = str(record.get("owner") or "package:" + str(record.get("package", "default")))
            name = str(record.get("name") or record["id"])
            if owner not in self.graph:
                self.add_package(owner.removeprefix("package:"))
            ids[("function", name)] = self.add_function(owner, name, **_attrs(record, "name", "id", "owner"))
        for record in semantics.get("variables", []):
            owner = str(record.get("owner") or "package:" + str(record.get("package", "default")))
            name = str(record.get("name") or record["id"])
            if owner not in self.graph:
                self.add_package(owner.removeprefix("package:"))
            ids[("variable", name)] = self.add_variable(owner, name, **_attrs(record, "name", "id", "owner"))
        for record in semantics.get("relationships", []):
            source = _resolve_id(str(record["source"]), ids, self.graph)
            target = _resolve_id(str(record["target"]), ids, self.graph)
            relationship = str(record.get("relationship", "depends_on"))
            self.add_relationship(source, target, relationship, **_attrs(record, "source", "target", "relationship"))

    def package_cycles(self) -> List[List[str]]:
        package_graph = nx.DiGraph()
        package_graph.add_nodes_from(self._nodes("package"))
        for source, target, data in self.graph.edges(data=True):
            if data.get("relationship") in {"contains", "calls", "uses", "depends_on", "imports", "references"}:
                source_package = self._package_for(source)
                target_package = self._package_for(target)
                if source_package and target_package and source_package != target_package:
                    package_graph.add_edge(source_package, target_package)
        return list(nx.simple_cycles(package_graph))

    def high_complexity_classes(self, threshold: int = 10) -> List[Dict[str, Any]]:
        results = []
        for node in self._nodes("class"):
            outgoing = ((_, _, data) for _, _, data in self.graph.out_edges(node, data=True))
            incoming = ((_, _, data) for _, _, data in self.graph.in_edges(node, data=True))
            degree = sum(1 for _, _, data in list(outgoing) + list(incoming)
                         if data.get("relationship") != "contains")
            if degree >= threshold:
                results.append({"id": node, "name": self.graph.nodes[node].get("name", node),
                                "complexity": degree, "threshold": threshold})
        return sorted(results, key=lambda item: (-item["complexity"], item["id"]))

    def uncalled_functions(self) -> List[str]:
        called: Set[str] = set()
        for source, target, data in self.graph.edges(data=True):
            if data.get("relationship") in {"calls", "invokes"}:
                called.add(target)
        return sorted(node for node in self._nodes("function")
                      if node not in called and not self.graph.nodes[node].get("entrypoint", False))

    def similarity(self, first: str, second: str) -> float:
        """Jaccard similarity of semantic neighbors/features for two nodes."""
        if first not in self.graph or second not in self.graph:
            raise KeyError("both nodes must be present")
        first_features = set(self.graph.successors(first)) | set(self.graph.predecessors(first))
        second_features = set(self.graph.successors(second)) | set(self.graph.predecessors(second))
        for node, features in ((first, first_features), (second, second_features)):
            features.update(self.graph.nodes[node].get("feature_tags", []))
        union = first_features | second_features
        return 1.0 if not union and first == second else len(first_features & second_features) / len(union or {None})

    def audit(self, complexity_threshold: int = 10) -> Dict[str, Any]:
        cycles = self.package_cycles()
        complex_classes = self.high_complexity_classes(complexity_threshold)
        uncalled = self.uncalled_functions()
        orphaned = [node for node, data in self.graph.nodes(data=True)
                    if data.get("level") != "package" and self.graph.in_degree(node) == 0]
        issues = []
        if cycles:
            issues.append({"type": "circular_dependency", "severity": "high", "count": len(cycles)})
        if complex_classes:
            issues.append({"type": "high_complexity_class", "severity": "medium", "count": len(complex_classes)})
        if uncalled:
            issues.append({"type": "uncalled_function", "severity": "low", "count": len(uncalled)})
        if orphaned:
            issues.append({"type": "orphaned_node", "severity": "low", "count": len(orphaned)})
        return {"issues": issues, "cycles": cycles, "high_complexity_classes": complex_classes,
                "uncalled_functions": uncalled, "orphaned_nodes": orphaned,
                "node_count": self.graph.number_of_nodes(), "edge_count": self.graph.number_of_edges()}

    def memory_map(self) -> Dict[str, Any]:
        """Return a JSON-safe hierarchy useful for UI memory-map views."""
        tree: Dict[str, Any] = {"level": "root", "children": {}}
        for node, data in self.graph.nodes(data=True):
            if data.get("level") != "package":
                continue
            package = {"id": node, "name": data.get("name", node), "level": "package", "children": {}}
            for child in nx.descendants(self._contains_graph(), node):
                child_data = self.graph.nodes[child]
                if child_data.get("level") in {"class", "function", "variable"}:
                    package["children"][child] = {"id": child, "name": child_data.get("name", child),
                                                    "level": child_data["level"]}
            tree["children"][node] = package
        return tree

    def _nodes(self, level: str) -> List[str]:
        return [node for node, data in self.graph.nodes(data=True) if data.get("level") == level]

    def _package_for(self, node: str) -> Optional[str]:
        if self.graph.nodes[node].get("level") == "package":
            return node
        packages = [parent for parent in nx.ancestors(self._contains_graph(), node)
                    if self.graph.nodes[parent].get("level") == "package"]
        return sorted(packages)[0] if packages else None

    def _contains_graph(self) -> nx.DiGraph:
        """Project only hierarchy edges for ownership and memory-map queries."""
        hierarchy = nx.DiGraph()
        hierarchy.add_nodes_from(self.graph.nodes)
        hierarchy.add_edges_from((source, target) for source, target, data in self.graph.edges(data=True)
                                 if data.get("relationship") == "contains")
        return hierarchy


def _attrs(record: Mapping[str, Any], *excluded: str) -> Dict[str, Any]:
    return {key: value for key, value in record.items() if key not in excluded}


def _resolve_id(value: str, aliases: Mapping[Tuple[str, str], str], graph: nx.Graph) -> str:
    if value in graph:
        return value
    for level in LEVELS:
        if (level, value) in aliases:
            return aliases[(level, value)]
    raise KeyError("unknown semantic node: " + value)


def audit_graph(graph: nx.Graph, complexity_threshold: int = 10) -> Dict[str, Any]:
    """Audit an existing graph using the same node attributes as the builder."""
    wrapper = SoftwareArchitectureGraph()
    wrapper.graph = graph
    return wrapper.audit(complexity_threshold)
