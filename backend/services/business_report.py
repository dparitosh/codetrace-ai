"""Self-contained business view of measured evidence and unimplemented projections."""
import html
import json
import math
from services.optimization_visuals import grouping_evidence
from services.product_line_optimizer import file_group_projection

def esc(value):
    return html.escape(str(value),quote=True)

def table(headers, rows):
    return '<div class="scroll"><table><thead><tr>'+''.join('<th scope="col">'+esc(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(cell)+'</td>' for cell in row)+'</tr>' for row in rows)+'</tbody></table></div>'

def reduction_summary(result):
    baseline,projection=result['baseline'],result['projection']
    def percentage(amount,total):
        if not total:return 'N/A'
        value=100*amount/total
        if 0<value<.0001:return '&lt;0.0001%'
        return f'{value:.4f}%' if 0<value<1 else f'{value:.2f}%'
    rows=[];charts=[]
    for metric,title,total in [('files','Files',baseline['eligible_files']),('lines','Physical source lines',baseline['physical_lines'])]:
        planning=projection['planning'][metric];upper=projection['upper'][metric]
        rows.append([title,f'{total:,}',f'{total-planning:,}',f'{planning:,}',percentage(planning,total),f'{upper:,}',percentage(upper,total)])
        maximum=max(2,math.ceil(upper/2)*2);bars=[]
        for index,(scenario,label,color) in enumerate([('low','Low','#7890a3'),('planning','Planning','#227ea2'),('upper','Upper envelope','#c38324')]):
            value=projection[scenario][metric];x=100+index*135;height=170*value/maximum
            bars.append(f'<rect x="{x}" y="{230-height}" width="65" height="{height}" fill="{color}"/><text x="{x+32}" y="{220-height}" text-anchor="middle">{value:,}</text><text x="{x+32}" y="257" text-anchor="middle">{label}</text>')
        charts.append(f'<article><h3>Projected {title.lower()} removed</h3><svg viewBox="0 0 550 300" role="img" aria-label="Projected {title.lower()} reduction: low {projection["low"][metric]}, planning {planning}, upper {upper}"><path d="M65 50V230H510" fill="none" stroke="#17334d"/><text x="55" y="235" text-anchor="end">0</text><text x="55" y="65" text-anchor="end">{maximum}</text>'+''.join(bars)+'<text x="285" y="290" text-anchor="middle">Reduction quantity (separate scale)</text></svg></article>')
    message='No supported reduction candidates were found in this snapshot.' if not projection['upper']['files'] and not projection['upper']['lines'] else 'These are candidate-based projections. No removal has been implemented or validated.'
    return '<h3>Projected reductions at a glance</h3><p class="notice">'+message+'</p><div class="twocol">'+''.join(charts)+'</div>'+table(['Measure','Current','Planning remaining','Planning removed','Planning reduction %','Upper removed','Upper reduction %'],rows)+'<p>Validated reduction: 0 files / 0 lines. Planning applies the stated adoption assumption; the upper envelope is not a promised result. Additional shared-module, import, configuration and test scaffolding is excluded.</p>'

def report_html(result, source):
    from services.optimization_report import chart_svg
    b,p=result['baseline'],result['projection']
    evidence=result.get('grouping_evidence') or grouping_evidence(result)
    units=[u['id'] for u in result['units']]
    files=[f for f in result['matrices']['files'] if f['eligible']]
    footprints={u:{f['path'] for f in files if u in f['memberships']} for u in units}
    pairs={frozenset((x['source'],x['target'])):x for x in evidence['unit_similarity']}
    threshold=evidence['threshold']; scope=evidence['code_scope']
    def coefficient(a,z):
        if a==z:return 1.0 if footprints[a] else None
        return pairs[frozenset((a,z))]['coefficient']
    heat=[]
    for a in units:
        row=[]
        for z in units:
            value=coefficient(a,z)
            color='white' if value is not None and value>.6 else '#17334d'
            shade='#edf2f7' if value is None else f'rgba(0,122,136,{.08+.82*value:.2f})'
            row.append(f'<td style="background:{shade};color:{color}" title="{esc(a)} / {esc(z)}">'+('N/A' if value is None else f'{value:.2f}')+'</td>')
        heat.append('<tr><th scope="row">'+esc(a)+'</th>'+''.join(row)+'</tr>')
    heatmap='<div class="scroll"><table class="heat"><thead><tr><th>Unit</th>'+''.join('<th>'+esc(u)+'</th>' for u in units)+'</tr></thead><tbody>'+''.join(heat)+'</tbody></table></div>'
    code_rows=[[esc(x['source']),esc(x['target']),f"{x['coefficient']:.3f}",f"{x['shared_declarations']}/{x['distinct_declarations']}"] for x in evidence['code_similarity'][:20]]
    code=table(['File A','File B','Code coefficient','Matching / distinct patterns'],code_rows) if code_rows else '<p class="notice">No positive declaration-fingerprint overlap found in compared files. Uncompared files are not scored zero.</p>'
    if evidence['code_similarity']:
        example=evidence['code_similarity'][0]
        patterns=[]
        for path in (example['source'],example['target']):
            mapping={}
            for function in result['matrices']['functions']:
                if function['path']==path and function.get('eligible') and function.get('fingerprint'):
                    mapping.setdefault((function['basis'],function['fingerprint']),set()).add(function['name'])
            patterns.append(mapping)
        a,z=set(patterns[0]),set(patterns[1]);shared=a&z
        ordered=sorted(a|z,key=lambda key:(key not in shared,key not in a,str(key)))
        pattern_rows=[[f'P{i+1}',esc(', '.join(sorted(patterns[0].get(key,()))) or '—'),esc(', '.join(sorted(patterns[1].get(key,()))) or '—'),'Shared' if key in shared else 'Only A' if key in a else 'Only B'] for i,key in enumerate(ordered[:8])]
        code_example=f'<p><strong>Measured example:</strong> A = {esc(example["source"].rsplit("/",1)[-1])}; B = {esc(example["target"].rsplit("/",1)[-1])}.</p>'+table(['Pattern identifier','Function in file A','Function in file B','Membership'],pattern_rows)+f'<ol><li>File A contains <strong>{len(a)}</strong> distinct patterns.</li><li>File B contains <strong>{len(z)}</strong> distinct patterns.</li><li>The files share <strong>{len(shared)}</strong> matching patterns.</li><li>Count the combined patterns once each: <strong>{len(a)} + {len(z)} − {len(shared)} = {len(a|z)}</strong>. The shared pattern is not counted twice.</li><li>Divide shared by combined: <strong>{example["shared_declarations"]} ÷ {example["distinct_declarations"]} = {example["coefficient"]:.3f}</strong>, or {100*example["coefficient"]:.1f}% overlap of distinct patterns.</li></ol><p>This percentage is not the percentage of code lines that can be removed.</p>'
        if len(ordered)>8:code_example+=f'<small>First 8 of {len(ordered)} pattern identifiers shown; calculation uses all patterns.</small>'
    else:
        code_example='<p><strong>Illustration only:</strong> A has {P1, P2}; B has {P1, P3}. There is 1 shared pattern (P1). The combined list has 3 distinct patterns, not 4, because P1 is counted once. Result: <strong>1 ÷ 3 = 0.333</strong>, or 33.3% pattern overlap. This is not a measured project result or a removal estimate.</p>'
    observed_pairs=[pair for pair in evidence['unit_similarity'] if pair['coefficient'] is not None]
    if observed_pairs:
        pair=max(observed_pairs,key=lambda pair:pair['coefficient'])
        dependency_example=f'<p><strong>Measured example:</strong> {esc(pair["source"])} and {esc(pair["target"])} share {pair["shared_files"]} files among {pair["distinct_files"]} distinct files: <strong>{pair["shared_files"]} ÷ {pair["distinct_files"]} = {pair["coefficient"]:.3f}</strong>.</p>'
    else: dependency_example='<p><strong>Illustration only:</strong> two units sharing 4 of 6 distinct dependency files have coefficient 4 ÷ 6 = 0.667. No measured pair is available in this snapshot.</p>'
    reductions=reduction_summary(result)
    # Identical preview population in both views, not two misleading samples.
    selected=set()
    for unit in units:selected.update(sorted(footprints[unit])[:2])
    selected.update(sorted(f['path'] for f in files if len(f['memberships'])>1)[:8])
    selected.update(sorted(f['path'] for f in files if not f['memberships'])[:5])
    selected=set(sorted(selected)[:60]); by_path={f['path']:f for f in files}
    def incidence(paths,columns):
        paths=list(paths);left=310;top=150;cell_width=48;cell_height=20
        width=max(1000,left+len(columns)*cell_width+30);height=top+len(paths)*cell_height+50
        plot=[f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="File dependency incidence matrix preview">']
        for j,unit in enumerate(columns):
            x=left+j*cell_width+cell_width/2
            plot.append(f'<text x="{x}" y="{top-15}" transform="rotate(-45 {x} {top-15})" font-size="13">{esc(unit)}</text>')
        for i,path in enumerate(paths):
            y=top+i*cell_height
            short='/'.join(path.split('/')[-2:])
            if len(short)>40:short=short[:37]+'…'
            plot.append(f'<text x="{left-10}" y="{y+14}" text-anchor="end" font-size="12"><title>{esc(path)}</title>{esc(short)}</text>')
            for j,unit in enumerate(columns):
                color='#007a88' if unit in by_path[path]['memberships'] else '#edf2f7'
                plot.append(f'<rect x="{left+j*cell_width}" y="{y}" width="{cell_width-2}" height="{cell_height-2}" fill="{color}"><title>{esc(path)} / {esc(unit)}: {int(unit in by_path[path]["memberships"])}</title></rect>')
        plot.append('</svg>')
        rows=[[esc(path)]+['1' if u in by_path[path]['memberships'] else '·' for u in columns] for path in paths]
        return ''.join(plot)+'<details><summary>Inspect exact filenames and memberships</summary>'+table(['File']+columns,rows)+'</details>'
    before=incidence(sorted(selected),sorted(units))
    after=incidence([path for path in result['roc']['rows'] if path in selected],result['roc']['columns'])
    assignment={u:i for i,c in enumerate(result['cells']) for u in c['units']}
    graph_units=[u for cell in result['cells'] for u in cell['units']]
    positions={u:(500+235*math.cos(2*math.pi*i/max(1,len(units))),300+235*math.sin(2*math.pi*i/max(1,len(units)))) for i,u in enumerate(graph_units)}
    colors=['#007a88','#8656a3','#b16c14','#2463a1','#377c47','#aa4e62']
    network=['<svg viewBox="0 0 1000 620" role="img" aria-label="Similarity network, node numbers identify formed cells"><rect width="1000" height="620" fill="#f7fafc"/>']
    for pair in evidence['unit_similarity']:
        score=pair['coefficient']
        if score is None or score<threshold:continue
        x,y=positions[pair['source']];xx,yy=positions[pair['target']]
        network.append(f'<line x1="{x}" y1="{y}" x2="{xx}" y2="{yy}" stroke="#7597a8" stroke-width="{1+4*score}"/><text x="{(x+xx)/2+40}" y="{(y+yy)/2+14}" text-anchor="middle" font-size="15">{score:.2f}</text>')
    for unit,(x,y) in positions.items():
        network.append(f'<circle cx="{x}" cy="{y}" r="24" fill="{colors[assignment[unit]%len(colors)]}"/><text x="{x}" y="{y+5}" text-anchor="middle" fill="white">{assignment[unit]+1}</text><text x="{x}" y="{y+45}" text-anchor="middle" font-size="13">{esc(unit)}</text>')
    network.append('</svg>')
    cards=[]
    for group in file_group_projection(result):
        if group['units']:
            paths=[f['path'] for f in files if {assignment[u] for u in f['memberships']}=={assignment[group['units'][0]]}]
        elif group['id']=='Unmapped':paths=[f['path'] for f in files if not f['memberships']]
        else:paths=[f['path'] for f in files if len({assignment[u] for u in f['memberships']})>1]
        cards.append('<article><h3>'+esc(group['id'])+'</h3><strong>'+str(group['current'])+' files</strong><p>'+esc(', '.join(group['units']) or 'Shared ownership or classification required')+'</p><ul>'+''.join('<li>'+esc(path)+'</li>' for path in sorted(paths)[:4])+'</ul><small>'+str(max(0,len(paths)-4))+' further files in detailed evidence</small></article>')
    formation=table(['Step','Unit','Decision','Similarity check'],[[i+1,esc(step['unit']),esc(step['action']+' '+step['cell']),esc('; '.join(c['unit']+': '+('N/A' if c['coefficient'] is None else f"{c['coefficient']:.3f}") for c in step['checks']) or 'First member starts a cell')] for i,step in enumerate(evidence['formation_steps'])])
    difference=table(['Measure','Current','Projected remaining','Difference'],[
        ['Eligible files',f"{b['eligible_files']:,}",f"{b['eligible_files']-p['planning']['files']:,}",f"−{p['planning']['files']:,}"],
        ['Physical source lines',f"{b['physical_lines']:,}",f"{b['physical_lines']-p['planning']['lines']:,}",f"−{p['planning']['lines']:,}"]])
    classification=result.get('classification',{})
    feature_groups=table(['Feature profile','Files','Functions'],[[esc(' + '.join(g['feature_ids'])),g['file_count'],g['function_count']] for g in classification.get('artifact_groups',[])]) if classification.get('artifact_groups') else '<p>No business feature grouping is established by this snapshot. Structural cells are candidates, not confirmed capability boundaries.</p>'
    actions=''.join('<article><h3>'+esc(c['kind'].replace('_',' '))+'</h3><p>Review '+esc(c['retained'] if isinstance(c['retained'],str) else c['retained']['path'])+'</p><p>Upper candidate reduction: <strong>'+str(c['net_upper_lines'])+' lines / '+str(c['files_upper'])+' files</strong>.</p><p>'+esc(c['evidence'])+'</p></article>' for c in result['candidates'][:12]) or '<p>No eligible duplicate removal candidates identified. Do not promise a reduction from grouping alone.</p>'
    llm=result.get('llm_review',{})
    if llm.get('status')=='advisory_only':
        advice=llm.get('review',{})
        model_summary='<p>Model: '+esc(llm.get('model','Not recorded'))+' · Advisory recommendations; references are checked, semantic correctness still requires review.</p><p>'+esc(advice.get('executive_review',''))+'</p><div class="cards">'+''.join('<article><h3>'+esc(item.get('title',item.get('sple_pattern','Refactoring recommendation')))+'</h3><p>'+esc(item.get('action',item.get('assessment','')))+'</p><p>'+esc(item.get('rationale',''))+'</p><p>Evidence: '+esc(', '.join(item.get('candidate_ids',[])+item.get('citation_ids',[])))+'</p><ul>'+''.join('<li>'+esc(check)+'</li>' for check in item.get('required_checks',[]))+'</ul></article>' for item in advice.get('recommendations',[]))+'</div>'
    else:
        model_summary='<p class="notice">LLM recommendations: '+esc(llm.get('status','not_requested'))+'. '+esc(llm.get('reason','No accepted live model review is included. Configure the AI provider and generate a new report with LLM recommendations enabled.'))+'</p>'
    raw=esc(json.dumps({'receipt':result['receipt'],'coverage':result['coverage'],'limitations':result['limitations'],'classification_preview':{k:(v[:50] if isinstance(v,list) else v) for k,v in classification.items()}},indent=2,ensure_ascii=False))
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Code optimization business assessment</title>
<style>body{{margin:0;font:16px/1.55 system-ui,sans-serif;background:#eef3f8;color:#17334d}}main{{max-width:1440px;margin:auto;padding:28px}}header{{background:#102e48;color:white;padding:32px;border-radius:16px}}nav{{display:flex;gap:12px;flex-wrap:wrap;margin:20px 0}}a{{color:#087789}}nav a{{background:white;padding:10px 16px;border-radius:24px;text-decoration:none}}section{{background:white;padding:26px;margin:20px 0;border:1px solid #d8e3ed;border-radius:14px}}h1,h2,h3{{line-height:1.2}}h1{{font-size:34px}}h2{{font-size:26px}}.matrixcompare{{display:grid;gap:16px;grid-template-columns:1fr}}.kpis,.cards,.twocol{{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}}article,.kpi{{padding:18px;border:1px solid #d8e3ed;border-radius:10px;background:#f8fbfe;overflow-wrap:anywhere}}.kpi strong{{display:block;font-size:32px}}.notice{{background:#fff4d9;border-left:5px solid #c38324;padding:16px}}.scroll{{overflow:auto}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{padding:10px;border:1px solid #d8e3ed;text-align:left;vertical-align:top}}th{{background:#edf3f8}}.heat td,.matrix td{{text-align:center}}.heat th{{min-width:90px}}.matrix{{max-height:560px}}.matrix th{{max-width:320px;overflow-wrap:anywhere}}.on{{background:#007a88;color:white}}.off{{color:#a7b7c5}}svg{{display:block;width:100%;height:auto}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;max-height:600px;overflow:auto}}small{{color:#536c82}}.formula{{font-size:20px;font-weight:600;color:#007a88}}@media(max-width:700px){{main{{padding:10px}}section,header{{padding:18px}}h1{{font-size:27px}}}}@media print{{nav{{display:none}}main{{padding:0}}section{{break-inside:auto}}.scroll{{overflow:visible}}}}</style></head><body><main>
<header><p>SOFTWARE PRODUCT LINE · GROUP TECHNOLOGY · CELLULAR GROUPING</p><h1>Where can this code be simplified?</h1><p>A visual assessment of current inventory, projected change, similarity evidence and proposed ownership cells.</p><small style="color:#d0e0ed">Source: {esc(source)} · Snapshot: {esc(result['receipt']['generated_at'])}</small></header>
<nav><a href="#difference">Business impact</a><a href="#similarity">Similarity</a><a href="#clustering">File clustering</a><a href="#cells">Cell formation</a><a href="#decisions">Recommended decisions</a><a href="#evidence">Supporting evidence</a></nav>
<section id="difference"><h2>1. Current versus projected: what changes?</h2><div class="kpis"><div class="kpi">Files assessed<strong>{b['eligible_files']:,}</strong></div><div class="kpi">Planning file reduction<strong>{p['planning']['files']:,}</strong></div><div class="kpi">Planning line reduction<strong>{p['planning']['lines']:,}</strong></div><div class="kpi">Proposed structural cells<strong>{len(result['cells'])}</strong></div></div>{reductions}<h3>LLM recommendations for these projected reductions</h3>{model_summary}<p class="notice">No source changes applied. Estimates are not achieved savings. Equal bars mean no supported whole-file removal; function consolidation may reduce lines while retaining every file.</p>{chart_svg(result)}{difference}<p>Planning adoption: {result['assumptions']['adoption_rate']:.0%}; upper candidate reduction: {p['upper']['lines']:,} lines / {p['upper']['files']:,} files. New extraction, configuration and test code can reduce or erase savings.</p></section>
<section id="similarity"><h2>2. Similarity: why group these together?</h2><div class="twocol"><article><h3>Dependency similarity</h3><p class="formula">J(A,B) = |A ∩ B| / |A ∪ B|</p><p>Shared files ÷ distinct files in both units</p>{dependency_example}<p>0 = no overlap; 1 = identical inventories; N/A = no evidence. Every pair in a cell must meet {threshold:.2f}.</p></article><article><h3>Code similarity coefficient</h3><p class="formula">J(A,B) = |F(A) ∩ F(B)| / |F(A) ∪ F(B)|</p><p><strong>In plain language:</strong> count the different function patterns shared by both files, then divide by the number of different patterns found across either file.</p><details><summary>What each symbol means</summary><ul><li>A and B are the two files being compared.</li><li>F(A) and F(B) are their sets of distinct extracted function-pattern fingerprints.</li><li>∩ means patterns present in both files.</li><li>∪ means patterns from either file, counting repeated identifiers once.</li><li>|…| means the number of items in that set.</li><li>J is the resulting overlap score: 0 means none; 1 means identical sets.</li></ul></details>{code_example}<p>Python uses name-normalized AST fingerprints; native declarations use exact parser fingerprints. This does not prove equivalent behavior, authorization or transactions.</p></article></div><h3>Dependency similarity heatmap</h3>{heatmap}<h3>Strongest observed code overlaps</h3><p>{scope['compared_files']} of {scope['files_with_fingerprints']} fingerprinted files compared; {scope['pairs_checked']:,} pairs checked. {scope['eligible_files']-scope['files_with_fingerprints']} files lack comparable fingerprints. Up to 20 positive pairs shown; absent pairs are not automatically zero.</p>{code}</section>
<section id="clustering"><h2>3. File clustering: before and after ordering</h2><p>The same {len(selected)} preview files are shown in both matrices. Filled squares mean dependency membership. Ordering exposes blocks; it does not change or remove code.</p><div class="matrixcompare"><article><h3>Before: alphabetical order</h3>{before}</article><article><h3>After: rank-order clustering</h3>{after}</article></div><p>{result['roc']['passes']} ordering passes; {'stable ordering reached' if result['roc']['converged'] else 'ordering did not converge within its bound'}. Full matrices are available below.</p></section>
<section id="cells"><h2>4. Cell formation and file clusters</h2><p>Node colors and numbers identify cells. Edges connect pairs meeting {threshold:.2f}; labels show coefficients. Connected chains alone do not justify a cell: every pair inside must pass.</p>{''.join(network)}<div class="cards">{''.join(cards)}</div><details><summary>See each cell-formation decision</summary>{formation}</details><h3>Business capability / feature groups</h3>{feature_groups}<p>Unmapped files require investigation; they are not deletion candidates.</p></section>
<section id="decisions"><h2>5. Recommended business decisions</h2><div class="cards">{actions}</div><ol><li>Confirm owners, capabilities and variation boundaries.</li><li>Pilot one candidate while preserving contracts and security/transaction boundaries.</li><li>Run representative product-configuration regression tests.</li><li>Measure net reduction after new scaffolding and prepare rollback evidence.</li></ol></section>
<section id="evidence"><h2>Supporting evidence — optional technical downloads</h2><p><strong>File CSV:</strong> file ownership/dependency membership. <strong>Function CSV:</strong> declarations with file-derived and observed callable membership. Business readers can use this report without opening either CSV.</p><p><a href="file-unit.csv">File matrix CSV</a> · <a href="function-unit.csv">Function matrix CSV</a> · <a href="analysis.json">Full assessment</a> · <a href="call-evidence.json">Call evidence</a> · <a href="receipt.json">Verification receipt</a></p><details><summary>Technical coverage, limitations and receipt</summary><pre>{raw}</pre></details></section></main></body></html>'''
