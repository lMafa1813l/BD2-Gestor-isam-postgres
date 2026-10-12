"""Valida evidencia completa y genera tablas LaTeX/figuras sin inventar mediciones."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics as stats
from collections import defaultdict

ROOT=Path(__file__).resolve().parents[1]

def median(values): return stats.median([float(x) for x in values])
def iqr(values):
    q=stats.quantiles([float(x) for x in values],n=4,method='inclusive')
    return q[2]-q[0]
def cell(rows,column,digits=3):
    vals=[r[column] for r in rows]
    return f'{median(vals):.{digits}f} [{iqr(vals):.{digits}f}]'
def load(path):
    metadata=json.loads(path.with_suffix('.json').read_text())
    if metadata.get('status')!='completed' or metadata.get('smoke') or metadata.get('reps',0)<5:
        raise ValueError(f'Evidencia incompleta, exploratoria o con menos de 5 repeticiones: {path}')
    if metadata.get('csv_sha256')!=hashlib.sha256(path.read_bytes()).hexdigest():
        raise ValueError(f'CSV no coincide con su hash: {path}')
    with path.open() as fh: rows=list(csv.DictReader(fh))
    if any(int(r['failed_transactions']) or int(r['transactions'])<=0 for r in rows):
        raise ValueError('Errores o cuotas vacías')
    return rows,metadata

def table(caption,headers,rows,label):
    result=['\\begin{table}[htbp]','\\centering\\small',f'\\caption{{{caption}}}\\label{{{label}}}',
            '\\resizebox{\\linewidth}{!}{%', '\\begin{tabular}{'+'l'+'r'*(len(headers)-1)+'}',
            '\\toprule',' & '.join(headers)+' \\\\','\\midrule']
    result+=[' & '.join(map(str,row))+' \\\\' for row in rows]
    result+=['\\bottomrule','\\end{tabular}}','\\end{table}','']
    return '\n'.join(result)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--bench',type=Path,default=ROOT/'docs/results/bench_corrected.csv')
    parser.add_argument('--overflow',type=Path,default=ROOT/'docs/results/overflow_corrected.csv')
    args=parser.parse_args()
    b,bm=load(args.bench);o,om=load(args.overflow)
    if set(bm['sizes'])!={100000,500000,1000000} or set(bm['datasets'])!={'d1','d2','d3'} or set(bm['configs'])!={'none','btree','isam'}:
        raise ValueError('Falta algún tamaño/dataset/configuración obligatorio')
    bg=defaultdict(list)
    for r in b:bg[r['dataset'],int(r['n']),r['config'],r['workload']].append(r)
    workloads=['w1_eq_uniform','w2_eq_absent','w4_range','w3_insert','w1_eq_after_inserts','w4_range_after_inserts']
    count=0
    for ds in ('d1','d2','d3'):
        for n in (100000,500000,1000000):
            for cfg in ('none','btree','isam'):
                for wl in workloads:
                    rows=bg[ds,n,cfg,wl]
                    if {int(x['rep']) for x in rows}!=set(range(1,bm['reps']+1)) or len(rows)!=bm['reps']:
                        raise ValueError(f'Replicas incompletas/duplicadas: {ds}/{n}/{cfg}/{wl}')
                    total=n//10 if wl=='w3_insert' else bm['range_queries'] if 'range' in wl else bm['eq_queries']
                    if any(int(x['transactions'])!=total for x in rows): raise ValueError('Cuota incorrecta')
                    expected=n+(n//10 if wl in ('w3_insert','w1_eq_after_inserts','w4_range_after_inserts') else 0)
                    if any(int(x['rows_after'])!=expected for x in rows): raise ValueError('Estado incorrecto de tabla')
                    count+=len(rows)
            for rep in range(1,bm['reps']+1):
                hashes={r['insert_fingerprint'] for cfg in ('none','btree','isam') for r in bg[ds,n,cfg,'w3_insert'] if int(r['rep'])==rep}
                if len(hashes)!=1 or '' in hashes: raise ValueError('Inserciones distintas entre alternativas')
    if len(b)!=count: raise ValueError('Observaciones extra fuera de la cuadrícula')
    og=defaultdict(list)
    for r in o:og[r['config'],r['step']].append(r)
    for cfg in om['configs']:
        steps=[str(x) for x in range(om['batches']+1)]+([] if 't' in cfg and cfg!='btree' else ['reindex'])
        for step in steps:
            rows=og[cfg,step]
            if len(rows)!=om['reps'] or {int(x['rep']) for x in rows}!=set(range(1,om['reps']+1)):
                raise ValueError(f'Trayectoria de overflow incompleta: {cfg}/{step}')
            expected=om['batch_rows']*(om['batches'] if step=='reindex' else int(step))
            if any(int(x['rows'])!=expected or int(x['transactions'])!=om['hot_queries'] for x in rows):
                raise ValueError('Cuota/estado de overflow incorrecto')
    out=ROOT/'docs/results';out.mkdir(parents=True,exist_ok=True)
    tex=[f'La corrida verificada contiene {len(b)} observaciones, {27*bm["reps"]} cargas independientes y {18*bm["reps"]} construcciones de índices. El IQR se indica entre corchetes. Todos los conteos y huellas entre alternativas fueron verificados.\n']
    tex.append('Versión registrada: '+bm['version'].replace('_','\\_')+'.\\par\n')
    rows=[]
    for ds in ('d1','d2','d3'):
        for n in (100000,500000,1000000):
            bt=bg[ds,n,'btree','w1_eq_uniform'];isa=bg[ds,n,'isam','w1_eq_uniform']
            rows.append([ds.upper(),f'{n:,}'.replace(',','\\,'),cell(bt,'build_ms'),cell(isa,'build_ms'),f"{median([r['index_bytes'] for r in bt])/2**20:.2f}",f"{median([r['index_bytes'] for r in isa])/2**20:.2f}"])
    tex.append(table('Construcción (ms): mediana [IQR], y tamaño inicial (MiB).', ['Datos','N','B-tree ms','ISAM ms','B-tree MiB','ISAM MiB'],rows,'tab:build'))
    for wl,title in [('w1_eq_uniform','Igualdad exitosa W1'),('w2_eq_absent','Igualdad ausente W2'),('w4_range','Rango W4'),('w3_insert','Inserción W3')]:
        rows=[]
        for ds in ('d1','d2','d3'):
            for n in (100000,500000,1000000):
                rs=[bg[ds,n,c,wl] for c in ('none','btree','isam')]
                rows.append([ds.upper(),f'{n:,}'.replace(',','\\,'),*[cell(x,'tps',0) for x in rs],*[cell(x,'lat_ms') for x in rs]])
        tex.append(table(title+': TPS y latencia media por réplica (ms), resumidos con mediana [IQR].', ['Datos','N','Sin TPS','B-tree TPS','ISAM TPS','Sin ms','B-tree ms','ISAM ms'],rows,'tab:'+wl))
    rows=[]
    for ds in ('d1','d2','d3'):
        for n in (100000,500000,1000000):
            bt=bg[ds,n,'btree','w1_eq_after_inserts'];isa=bg[ds,n,'isam','w1_eq_after_inserts']
            rows.append([ds.upper(),f'{n:,}'.replace(',','\\,'),f'{1.1*n:.0f}',f"{median([r['index_bytes'] for r in bt])/2**20:.2f}",f"{median([r['index_bytes'] for r in isa])/2**20:.2f}",cell(isa,'overflow_blocks',0),cell(isa,'longest_chain',0)])
    tex.append(table(r'Estado después de insertar exactamente un 10\% de filas; tamaños en MiB.', ['Datos','N inicial','Filas finales','B-tree MiB','ISAM MiB','Overflow ISAM','Cadena ISAM'],rows,'tab:after'))
    ratios=[median([r['tps'] for r in bg[ds,n,'isam','w1_eq_uniform']])/median([r['tps'] for r in bg[ds,n,'btree','w1_eq_uniform']]) for ds in ('d1','d2','d3') for n in (100000,500000,1000000)]
    tex.append(f'En W1, el cociente de medianas TPS ISAM/B-tree se encuentra entre {min(ratios):.3f} y {max(ratios):.3f}. Es una descripción de esta corrida y de este protocolo, sin prueba de equivalencia estadística. Las tablas de construcción distinguen cinco reconstrucciones efectivas; los tiempos repetidos en filas de otros workloads de la misma réplica no se cuentan como reconstrucciones adicionales.\n')
    pairs=[(ds,n) for ds in ('d1','d2','d3') for n in (100000,500000,1000000)]
    build_ratios=[median([r['build_ms'] for r in bg[ds,n,'isam','w1_eq_uniform']])/median([r['build_ms'] for r in bg[ds,n,'btree','w1_eq_uniform']]) for ds,n in pairs]
    saving=[100*(1-median([r['index_bytes'] for r in bg[ds,n,'isam','w1_eq_uniform']])/median([r['index_bytes'] for r in bg[ds,n,'btree','w1_eq_uniform']])) for ds,n in pairs]
    range_ratios=[median([r['tps'] for r in bg[ds,n,'isam','w4_range']])/median([r['tps'] for r in bg[ds,n,'btree','w4_range']]) for ds,n in pairs]
    insert_ratios=[median([r['tps'] for r in bg[ds,n,'isam','w3_insert']])/median([r['tps'] for r in bg[ds,n,'btree','w3_insert']]) for ds,n in pairs]
    tex.append(f'La mediana de construcción de ISAM fue menor que la de B-tree en {sum(x<1 for x in build_ratios)} de nueve combinaciones de datos y tamaño. El cociente de tiempos ISAM/B-tree varió entre {min(build_ratios):.3f} y {max(build_ratios):.3f}; no se infiere la misma ventaja para otros entornos o construcción paralela.\n')
    tex.append(f'El ahorro inicial de tamaño de ISAM frente a B-tree estuvo entre {min(saving):.2f} y {max(saving):.2f}\\%. Este resultado es compatible con entradas compactas de 12 bytes y ausencia de un item identifier por entrada en el layout ISAM. Se refiere a claves iniciales únicas y a los rellenos configurados; no demuestra la misma relación con duplicados arbitrarios.\n')
    tex.append(f'En rangos el cociente de TPS ISAM/B-tree varió entre {min(range_ratios):.3f} y {max(range_ratios):.3f}; en inserciones por fila, entre {min(insert_ratios):.3f} y {max(insert_ratios):.3f}. La organización física del heap, el plan elegido y el costo de recuperar payload influyen junto con el índice. No se atribuye toda diferencia a una única causa sin instrumentación adicional.\n')
    maximum_overflow=max(int(r['overflow_blocks']) for r in b if r['config']=='isam' and r['workload']=='w3_insert')
    tex.append(f'Después de la inserción uniforme del 10\\%, el máximo de páginas de overflow observado en el barrido principal fue {maximum_overflow}. La holgura inicial del 20\\% puede absorber esta carga; para exponer el caso desfavorable se necesita el experimento concentrado siguiente. Una carga sin cadenas largas no demuestra inmunidad a overflow.\n')
    tex.append('\\clearpage\n')
    (out/'benchmark-tables.tex').write_text('\n'.join(tex))
    ot=[f'Overflow adicional: N inicial = {om["n"]}, {om["reps"]} trayectorias independientes por configuración, {om["batches"]} lotes de {om["batch_rows"]} filas y {om["hot_queries"]} consultas calientes por punto.\n']
    rows=[]
    last=str(om['batches'])
    for cfg in om['configs']:
        initial=og[cfg,'0'];fin=og[cfg,last];rei=og.get((cfg,'reindex'))
        rows.append([cfg,cell(initial,'eq_lat_ms'),cell(fin,'eq_lat_ms'),cell(fin,'longest_chain',0),cell(rei,'eq_lat_ms') if rei else '--',cell(rei,'reindex_ms') if rei else '--'])
    ot.append(table('Lectura caliente inicial, final y después de REINDEX: mediana [IQR].', ['Configuración','Inicial ms','Final ms','Cadena final','Tras REINDEX ms','REINDEX ms'],rows,'tab:overflow'))
    rows=[]
    for cfg in om['configs']:
        cfg_rows=[r for r in o if r['config']==cfg and r['step'] not in ('0','reindex')]
        insert_totals=[sum(float(r['insert_ms']) for r in cfg_rows if int(r['rep'])==rep) for rep in range(1,om['reps']+1)]
        reindex_totals=[sum(float(r['reindex_ms']) for r in cfg_rows if int(r['rep'])==rep) for rep in range(1,om['reps']+1)]
        rows.append([cfg,f'{stats.median(insert_totals):.3f}',f'{stats.median(reindex_totals):.3f}',f'{stats.median([a+b for a,b in zip(insert_totals,reindex_totals)]):.3f}',f"{median([r['index_bytes'] for r in og[cfg,last]])/2**20:.2f}"])
    ot.append(table('Costo acumulado por trayectoria (medianas, ms) antes del REINDEX final de comparación.', ['Configuración','Inserción','Política REINDEX','Suma de costos','MiB finales'],rows,'tab:policy'))
    ot.append('Los costos de la política se suman por réplica antes de calcular la mediana. Una latencia final cercana a B-tree no significa regresar a la latencia inicial: las inserciones aumentan la cantidad de resultados. La eliminación de overflow tampoco implica siempre menor tamaño físico.\n')
    if ('isam80',last) in og and ('isam80','reindex') in og:
        before=median([r['eq_lat_ms'] for r in og['isam80',last]])
        after=median([r['eq_lat_ms'] for r in og['isam80','reindex']])
        initial=median([r['eq_lat_ms'] for r in og['isam80','0']])
        longest=median([r['longest_chain'] for r in og['isam80',last]])
        ot.append(f'ISAM80 pasó de una mediana de {initial:.3f} ms a {before:.3f} ms, con cadena final mediana de {longest:.0f} páginas. Tras REINDEX registró {after:.3f} ms: cambio de {100*(1-after/before):.2f}\\% respecto del estado degradado. La mejora combina eliminación de cadenas y reorganización; la lectura de más filas y páginas del heap persiste.\n')
    import os
    os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'))
    os.environ.setdefault('XDG_CACHE_HOME',str(ROOT/'.cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figures=out/'figures';figures.mkdir(exist_ok=True)
    for wl,name,title in [('w1_eq_uniform','igualdad','Igualdad exitosa'),('w4_range','rango','Búsqueda por rango')]:
        fig,axes=plt.subplots(1,3,figsize=(11,3.5),sharey=True)
        for ax,ds in zip(axes,('d1','d2','d3')):
            for cfg,color in [('none','#888888'),('btree','#3465a4'),('isam','#c34a36')]:
                vals=[median([r['lat_ms'] for r in bg[ds,n,cfg,wl]]) for n in (100000,500000,1000000)]
                ax.plot([100,500,1000],vals,marker='o',label=cfg,color=color)
            ax.set(title=ds.upper(),xlabel='Miles de filas');ax.set_yscale('log');ax.grid(alpha=.2)
        axes[0].set_ylabel('Mediana de latencia media (ms)');axes[0].legend();fig.suptitle(title+'; cinco repeticiones independientes');fig.tight_layout();fig.savefig(figures/f'{name}.pdf');plt.close(fig)
        tex.append(f'\\begin{{figure}}[htbp]\\centering\\includegraphics[width=\\linewidth]{{docs/results/figures/{name}.pdf}}\\caption{{{title}: escalabilidad observada bajo el protocolo registrado.}}\\end{{figure}}\n')
    (out/'benchmark-tables.tex').write_text('\n'.join(tex))
    fig,ax=plt.subplots(figsize=(8,4))
    for cfg in om['configs']:
        steps=[str(x) for x in range(om['batches']+1)]
        values=[median([r['eq_lat_ms'] for r in og[cfg,s]]) for s in steps]
        ax.plot([int(s)*om['batch_rows']/1000 for s in steps],values,marker='o',label=cfg)
    ax.set(xlabel='Miles de filas insertadas',ylabel='Mediana de latencia media caliente (ms)',title='Concentración y reorganización; cinco trayectorias')
    ax.legend();ax.grid(alpha=.2);fig.tight_layout();fig.savefig(figures/'overflow.pdf');plt.close(fig)
    ot.append('\\begin{figure}[htbp]\\centering\\includegraphics[width=.95\\linewidth]{docs/results/figures/overflow.pdf}\\caption{Latencia caliente por lote. Los puntos de políticas incluyen el estado posterior a reorganizar.}\\end{figure}\n\\clearpage\n')
    (out/'overflow-tables.tex').write_text('\n'.join(ot))
    # El archivo principal también conserva todas las tablas numéricas en línea.
    # Los marcadores permiten actualizar únicamente los resultados generados.
    report=ROOT/'report.tex'
    content=report.read_text()
    fragments=[
        ('BENCHMARK', '\\IfFileExists{docs/results/benchmark-tables.tex}{\\input{docs/results/benchmark-tables.tex}}{\n\\textbf{Las mediciones corregidas están en ejecución. Esta versión no debe\npresentarse como informe de resultados final hasta generar las tablas completas.}}', '\n'.join(tex)),
        ('OVERFLOW', '\\IfFileExists{docs/results/overflow-tables.tex}{\\input{docs/results/overflow-tables.tex}}{\n\\textbf{Pendiente incorporar el experimento corregido completo de overflow.}}', '\n'.join(ot)),
    ]
    for name,fallback,body in fragments:
        start=f'% BEGIN GENERATED {name}\n';end=f'% END GENERATED {name}'
        replacement=start+body+'\n'+end
        if start in content:
            left=content.index(start);right=content.index(end,left)+len(end)
            content=content[:left]+replacement+content[right:]
        elif fallback in content:
            content=content.replace(fallback,replacement,1)
        else:
            raise ValueError(f'No se encontró el bloque de resultados {name}; conservar el informe y revisar sus marcadores')
    report.write_text(content)
    (out/'validation.json').write_text(json.dumps({'status':'validated','benchmark_observations':len(b),'overflow_observations':len(o),'independent_runs':27*bm['reps'],'independent_index_builds':18*bm['reps'],'benchmark_csv_sha256':bm['csv_sha256'],'overflow_csv_sha256':om['csv_sha256']},indent=2))
    print('Evidencia completa validada; tablas y figuras generadas en docs/results/')

if __name__=='__main__': main()
