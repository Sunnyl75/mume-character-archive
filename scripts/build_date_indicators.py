#!/usr/bin/env python3
"""Build a portable chronology page and separate WordPress plugin, without publishing."""
import argparse
from datetime import date
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def validate(data):
    if data.get('schema') != 'mume-date-indicators/1': raise ValueError('Invalid catalogue schema')
    for key in ('sources', 'epochs', 'indicators'):
        ids = set()
        for row in data[key]:
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,150}', row['id']) or row['id'] in ids: raise ValueError('Invalid or duplicate ' + key + ' identity')
            ids.add(row['id'])
            for name in ('start', 'end', 'date_start', 'date_end', 'documented_date'):
                if row.get(name): date.fromisoformat(row[name])
            if row.get('date_start') and row.get('date_end') and row['date_start']>row['date_end']: raise ValueError('Source date range reversed')
    sources = {s['id'] for s in data['sources']}
    for indicator in data['indicators']:
        if indicator['mode'] not in {'introduced_by','observed_by','transition','unresolved','lineage','documented'}: raise ValueError('Unknown indicator mode')
        if indicator['status'] not in {'documented','provisional','unresolved'}: raise ValueError('Unknown indicator status')
        for observation in indicator['attestations']:
            if observation['source_id'] not in sources: raise ValueError('Unknown evidence source')
    return data


def build(catalogue, output):
    data = validate(json.loads(catalogue.read_text()))
    assets = ROOT/'site/date-indicators'
    css = (assets/'style.css').read_text()
    js = (assets/'chronology.js').read_text()
    encoded = json.dumps(data, ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    html = '<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MUME Dating Indicators — Bree Legends</title><style>body{margin:0;background:#f2eee3}'+css+'</style></head><body><div class="bree-mume-dates"><div class="mdi-app"><noscript>Enable JavaScript to sort and inspect the chronology.</noscript></div></div><script>window.MUME_DATE_INDICATORS='+encoded+';</script><script>'+js+'</script></body></html>\n'
    output.mkdir(parents=True, exist_ok=True)
    page = output/'MUME_Date_Indicators.html';page.write_text(html)
    plugin = output/'bree-mume-date-indicators-0.1.0.zip'
    with zipfile.ZipFile(plugin,'w',zipfile.ZIP_DEFLATED) as archive:
        files = {'bree-mume-date-indicators.php':(ROOT/'integrations/wordpress/bree-mume-date-indicators/bree-mume-date-indicators.php').read_bytes(),
                 'public/style.css':css.encode(), 'public/chronology.js':js.encode(),
                 'public/catalogue.json':(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode(),
                 'readme.txt':(ROOT/'integrations/wordpress/bree-mume-date-indicators/readme.txt').read_bytes()}
        for name,content in files.items():
            info=zipfile.ZipInfo('bree-mume-date-indicators/'+name,(2026,11,6,0,0,0));info.create_system=3;info.external_attr=0o100644<<16;info.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(info,content)
    print(page);print(plugin)
    return page,plugin


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalogue',type=Path,default=ROOT/'research/date_indicators.json')
    parser.add_argument('--output',type=Path,default=ROOT/'releases')
    args=parser.parse_args();build(args.catalogue,args.output)
