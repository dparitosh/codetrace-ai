"""Shared standalone report/chart artifacts for API exports and read-only CLI."""
import hashlib
import html
import json
from services.product_line_optimizer import csv_matrix, digest


def chart_svg(result):
    from services.product_line_optimizer import file_group_projection
    import math
    groups=file_group_projection(result)
    maximum=max([g['current'] for g in groups]+[1])
    step=max(1,math.ceil(maximum/5));top=step*5
    width=max(1100,140*len(groups)+160);left=90;right=width-35;bottom=440;height=300
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="640" viewBox="0 0 {width} 640" role="img" aria-labelledby="title desc">',
        '<title id="title">Current and projected file quantities by group</title>',
        '<desc id="desc">X-axis: disjoint GT cell file groups. Y-axis: eligible file quantity. Projected counts use planning whole-file removal only.</desc>',
        f'<rect width="{width}" height="640" fill="#f5f8fc"/>',
        '<g font-family="sans-serif" fill="#17334d"><text x="30" y="36" font-size="23">Current and projected file quantities by group</text>',
        '<rect x="90" y="68" width="18" height="18" fill="#227ea2"/><text x="117" y="83" font-size="15">Current</text>',
        '<rect x="245" y="68" width="18" height="18" fill="#c38324"/><text x="272" y="83" font-size="15">Projected (planning)</text>',
        '<text x="25" y="290" transform="rotate(-90 25 290)" text-anchor="middle" font-size="16">File quantity</text>']
    for tick in range(6):
        value=tick*step;y=bottom-height*value/top
        parts.append(f'<path d="M{left} {y}H{right}" stroke="#d9e2ec"/><text x="{left-12}" y="{y+5}" text-anchor="end" font-size="14">{value:,}</text>')
    parts.append(f'<path d="M{left} 140V{bottom}H{right}" fill="none" stroke="#17334d" stroke-width="2"/>')
    band=(right-left)/max(1,len(groups));bar=min(38,band*.28)
    for i,group in enumerate(groups):
        center=left+band*(i+.5)
        for j,(key,color) in enumerate([('current','#227ea2'),('projected','#c38324')]):
            value=group[key];h=height*value/top;x=center+(-bar-3 if j==0 else 3)
            parts.append(f'<rect x="{x:.2f}" y="{bottom-h:.2f}" width="{bar:.2f}" height="{h:.2f}" fill="{color}"><title>{html.escape(group["id"])}: {key} {value}</title></rect><text x="{x+bar/2:.2f}" y="{bottom-h-9:.2f}" text-anchor="middle" font-size="13">{value:,}</text>')
        label=html.escape(group['id'])
        parts.append(f'<text x="{center:.2f}" y="465" transform="rotate(25 {center:.2f} 465)" font-size="13">{label}</text>')
    parts.extend([f'<text x="{width/2}" y="550" text-anchor="middle" font-size="17">File groups (GT cells, shared and unmapped)</text>',
        '<text x="30" y="591" font-size="14">Each eligible file is counted once. Projected = current minus planning whole-file removals.</text>',
        '<text x="30" y="617" font-size="14">Equal bars mean no supported whole-file reduction; declaration-line savings do not remove files.</text></g></svg>'])
    return ''.join(parts)


def report_html(result, source):
    from services.business_report import report_html as render
    return render(result,source)


def assessment_documents(result, source):
    return {'analysis.json':json.dumps(result,indent=2,ensure_ascii=False).encode('utf-8'),
        'file-unit.csv':csv_matrix(result,'files').encode('utf-8-sig'),
        'function-unit.csv':csv_matrix(result,'functions').encode('utf-8-sig'),
        'call-evidence.json':json.dumps(result['matrices']['calls'],indent=2).encode('utf-8'),
        'reduction-chart.svg':chart_svg(result).encode('utf-8'),
        'report.html':report_html(result,str(source)).encode('utf-8')}


def write_artifacts(result, output, source):
    result['receipt']['analysis_sha256']=digest({k:v for k,v in result.items() if k!='receipt'})
    output.mkdir(parents=True,exist_ok=True)
    artifacts=assessment_documents(result,source)
    for name,body in artifacts.items(): (output/name).write_bytes(body)
    receipt={**result['receipt'],'artifacts':{name:hashlib.sha256(body).hexdigest() for name,body in artifacts.items()}}
    (output/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
