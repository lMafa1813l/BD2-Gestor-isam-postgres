"""Validate completed distributed runs and report medians and inclusive IQRs."""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path
import statistics as st
import zipfile


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def load(directory):
    metadata=json.loads((directory/'metadata.json').read_text())
    if metadata.get('status')!='completed' or metadata.get('smoke') or metadata.get('reps',0)<5 or metadata.get('n',0)<1000000:
        raise ValueError(f'Not an official completed run: {directory}')
    path=directory/'trials.csv'
    if digest(path)!=metadata['csv_sha256']:
        raise ValueError('CSV hash mismatch')
    rows=list(csv.DictReader(path.open()))
    expected=metadata['reps']*len(metadata['strategies'])*len(metadata['configs'])*len(metadata['profiles'])*len(metadata['latency_modes'])
    if len(rows)!=expected or metadata['observations']!=expected:
        raise ValueError('Incomplete experiment matrix')
    archive=zipfile.ZipFile(directory/'evidence.zip') if (directory/'evidence.zip').exists() else None
    try:
        for name,expected_hash in metadata['artifacts_sha256'].items():
            content=(directory/name).read_bytes() if (directory/name).exists() else archive.read(name)
            if hashlib.sha256(content).hexdigest()!=expected_hash:raise ValueError(f'Artifact hash mismatch: {name}')
    finally:
        if archive:archive.close()
    grouped=defaultdict(list)
    fingerprints=set()
    ops_hashes={}
    for row in rows:
        if min(int(row['rx_bytes']),int(row['tx_bytes']))<0:raise ValueError('Negative network byte delta')
        if int(row['failures']) or int(row['reads'])*10!=int(row['operations'])*7 or int(row['writes'])*10!=int(row['operations'])*3 or int(row['sum_status'])!=int(row['writes']):
            raise ValueError('Failed transaction, wrong mix or uncommitted writes')
        grouped[tuple(row[k] for k in ('latency_mode','strategy','config','profile'))].append(row)
        key=(row['rep'],row['profile'])
        if ops_hashes.setdefault(key,row['input_sha256'])!=row['input_sha256']:
            raise ValueError('Unequal logical operations')
        fingerprints.add(row['fingerprint'])
    if len(fingerprints)!=1:raise ValueError('Unequal initial datasets')
    for key,group in grouped.items():
        if len(group)!=metadata['reps'] or {int(r['rep']) for r in group}!=set(range(1,metadata['reps']+1)):
            raise ValueError(f'Missing/duplicate repetitions: {key}')
    return rows,metadata


def median(rows,key):return st.median(float(r[key]) for r in rows)


def cell(rows,key,digits=3):
    values=[float(r[key]) for r in rows]
    q=st.quantiles(values,n=4,method='inclusive')
    return f'{st.median(values):.{digits}f} [{q[2]-q[0]:.{digits}f}]'


def tex_escape(value):
    return str(value).replace('_',r'\_').replace('%',r'\%')


def table(caption,headers,rows):
    lines=[r'\begin{table}[htbp]',r'\centering\small',r'\caption{'+caption+'}',
           r'\resizebox{\linewidth}{!}{%',r'\begin{tabular}{'+'l'*len(headers)+'}',
           r'\toprule',' & '.join(map(tex_escape,headers))+r' \\',r'\midrule']
    lines+=[' & '.join(map(tex_escape,row))+r' \\' for row in rows]
    return '\n'.join(lines+[r'\bottomrule',r'\end{tabular}}',r'\end{table}'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runs',nargs='+',type=Path)
    parser.add_argument('--validation',type=Path)
    parser.add_argument('--out',type=Path,default=Path('docs/results/distributed'))
    args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    all_rows=[];metas=[]
    for directory in args.runs:
        rows,meta=load(directory);all_rows+=rows;metas.append(meta)
    keys=[tuple(row[k] for k in ('latency_mode','strategy','config','profile','rep')) for row in all_rows]
    if len(keys)!=len(set(keys)):raise ValueError('Overlapping experiments')
    g=defaultdict(list)
    for row in all_rows:g[tuple(row[k] for k in ('latency_mode','strategy','config','profile'))].append(row)
    headers=['Modo','Estrategia','Índice secundario','Perfil','Total ms','SQL real ms','Modelo ms','RX MiB','TX MiB']
    rows=[]
    for key,group in sorted(g.items()):
        rows.append([*key,cell(group,'mean_elapsed_ms'),cell(group,'mean_db_ms'),cell(group,'mean_model_ms'),
                     f'{median(group,"rx_bytes")/2**20:.3f}',f'{median(group,"tx_bytes")/2**20:.3f}'])
    text=[f'Se validaron {len(all_rows)} ensayos independientes con N=1\\,000\\,000 pedidos y cinco repeticiones por condición. Cada ensayo contiene 100 operaciones (70 lecturas y 30 escrituras).',
          'Se reporta mediana [IQR] entre réplicas. SQL real mide el tiempo observado de ejecutar y recuperar el resultado; total incluye la espera de latencia simulada. RX/TX incluyen tráfico de cliente y FDW, y no deben sumarse como bytes útiles únicos.',
          table('Resultados distribuidos: mediana [IQR] de la latencia media por ensayo; transferencia mediana por ensayo.',headers,rows)]
    build_rows=[];detail_rows=[]
    for key,group in sorted(g.items()):
        build_rows.append([*key,cell(group,'build_ms'),f'{median(group,"secondary_index_bytes")/2**20:.3f}',
                           cell(group,'remote_operations',0),cell(group,'origin_c_operations',0)])
        for kind in ('customer','range','write'):
            detail_rows.append([*key,kind,cell(group,kind+'_db_ms'),cell(group,kind+'_elapsed_ms')])
    text += [table('Construcción del índice secundario (suma de tres nodos), espacio y encaminamiento.',
        ['Modo','Estrategia','Índice','Perfil','Build ms','Índice MiB','Ops remotas','Ops origen C'],build_rows),
        table('Desglose por operación: mediana [IQR] de la latencia media, en ms.',
        ['Modo','Estrategia','Índice','Perfil','Operación','SQL real','Total'],detail_rows)]
    validation=None
    if args.validation:
        validation=json.loads((args.validation/'metadata.json').read_text())
        if validation['status']!='completed' or validation['smoke'] or validation['n']<1000000 or validation['reps']<5:
            raise ValueError('Incomplete official acceptance tests')
        for entry in validation['scenarios']:
            path=args.validation/entry['file']
            if digest(path)!=entry['sha256']:raise ValueError('Acceptance evidence hash mismatch')
            v=json.loads(path.read_text())
            if v['status']!='passed' or len(v['outage']['expected_failures'])!=2 or v['outage']['recovery']!='passed':
                raise ValueError('Acceptance scenario failed')
        text.append(f'Las {len(validation["scenarios"])} validaciones oficiales de réplica e indisponibilidad terminaron correctamente. A/B conservaron lecturas y una escritura local; el total global y la escritura hacia C fallaron con C detenido. Después de reiniciar C se verificaron los datos y la única escritura confirmada.')
    # Plots use only validated observations; no extrapolated values.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for ax,profile in zip(axes,('balanced','hot_c')):
        for strategy,color in [('regional','#2166ac'),('hash','#b2182b')]:
            groups=[g['model',strategy,cfg,profile] for cfg in ('none','btree','isam')]
            vals=[median(rs,'mean_elapsed_ms') for rs in groups]
            ax.plot(['none','btree','isam'],vals,marker='o',label=strategy,color=color)
        ax.set(title=profile,xlabel='Índice secundario',ylabel='Mediana de latencia media total (ms)');ax.grid(alpha=.2);ax.legend()
    fig.tight_layout();fig.savefig(args.out/'latency.pdf');plt.close(fig)
    text.append(r'\begin{figure}[htbp]\centering\includegraphics[width=\linewidth]{docs/results/distributed/latency.pdf}\caption{Tiempo total bajo el modelo aditivo de latencias. Incluye consultas reales y espera simulada.}\end{figure}')
    (args.out/'summary.tex').write_text('\n\n'.join(text)+'\n')
    md=['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']
    md+=['| '+' | '.join(row)+' |' for row in rows]
    (args.out/'summary.md').write_text('\n'.join(md)+'\n')
    (args.out/'validation.json').write_text(json.dumps(dict(status='validated',trials=len(all_rows),
        workload_operations=sum(int(r['operations']) for r in all_rows),n=metas[0]['n'],
        acceptance_scenarios=len(validation['scenarios']) if validation else 0,
        input_csv_sha256=[m['csv_sha256'] for m in metas]),indent=2)+'\n')
    print('Validated reports: '+str(args.out))


if __name__=='__main__':main()
