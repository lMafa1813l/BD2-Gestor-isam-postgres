"""Set up and inspect the dedicated three-node lab without running benchmarks."""
import argparse
import json

import db


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('setup','demo'))
    parser.add_argument('--n',type=int,default=1000000)
    parser.add_argument('--strategy',choices=db.STRATEGIES,default='regional')
    parser.add_argument('--index',choices=db.INDEXES,default='isam')
    parser.add_argument('--smoke',action='store_true')
    args=parser.parse_args()
    if args.n<1000000 and not args.smoke:
        parser.error('Use --smoke to label a setup smaller than 1M orders')
    conns=db.connect_all()
    try:
        if args.action=='setup':
            print(json.dumps(db.setup(conns,args.n,args.strategy,args.index),indent=2))
            print(json.dumps(db.validate(conns,args.n,args.strategy),indent=2))
        else:
            for node,conn in conns.items():
                print(node.upper(), 'local orders/catalog version:',conn.execute('SELECT count(*),(SELECT version FROM dist.replica_state) FROM dist.orders').fetchone())
                print(node.upper(), 'global FDW orders:',conn.execute('SELECT count(*) FROM dist.all_orders').fetchone()[0])
            print('A: actual FDW plan:',json.dumps(conns['a'].execute('EXPLAIN (ANALYZE, VERBOSE, FORMAT JSON) SELECT count(*) FROM remote_b.orders').fetchone()[0],indent=2))
    finally:
        for conn in conns.values():conn.close()


if __name__=='__main__': main()
