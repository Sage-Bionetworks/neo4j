import synapseclient
import load2Neo4jDB as ndb
import convertSynapse2Graph as cg
import multiprocessing.dummy as mp
import threading
import argparse
import logging
import json
from collections import OrderedDict
from py2neo import Graph, authenticate

syn = synapseclient.login()

if __name__ == '__main__':
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    parser = argparse.ArgumentParser(description=
                '''Please input [1] the synapse ID or space-separated list of synapse ID and
                            [2, default: graph.json] the name of json outfile to graph provenance and
                            [3, default: # of available cores] the mp pool size''')
    parser.add_argument('id', metavar='synId', nargs='+', help='Input the synapse ID or list of synapse IDs')
    parser.add_argument('--j', metavar='json', help='Input name of json outfile')
    parser.add_argument('--p', type=int, help='Specify the pool size for the multiprocessing module')
    parser.add_argument('-l', action='store_true', default=False, help='Load data from json file to Neo4j database')
    args = parser.parse_args()

    proj_inputs = args.id
    if args.j:
        json_file = args.j
    else:
        json_file = 'graph.json'
    if args.p:
        p = mp.Pool(args.p)
    else:  
        p = mp.Pool()
    nodes = dict()

    for proj in proj_inputs:
        print 'Getting entities from %s' %proj
        nodes.update(cg.getEntities(projectId = proj))
    logging.info('Fetched %i entities' %len(nodes))

    activities = p.map(cg.safeGetActivity, nodes.items())
    activities = cg.cleanUpActivities(activities)
    if len(activities) > 0:
        print '%i activities found i.e. %f%% entities have provenance' %(len(activities),
                                                                            float(len(nodes))/len(activities))
    else:
        print 'This project lacks accessible information on provenance'

    edges = cg.buildEdgesfromActivities(nodes, activities)
    logging.info('I have  %i nodes and %i edges' %(len(nodes), len(edges)))
    with open(json_file, 'w') as fp:
        json.dump(OrderedDict([('vertices', nodes.values()), ('edges', edges)]), fp, indent=4)

    if args.l:
        logging.info('Connecting to Neo4j and authenticating user credentials')
        with open('credentials.json') as creds:
            db_info=json.load(creds)
        authenticate(db_info['machine'], db_info['username'], db_info['password'])
        db_dir = db_info['machine'] + "/db/data"
        graph = Graph(db_dir)

        try:
            ndb.json2neo4j(str(json_file), graph)
        except:
            logging.error('Error involving loading data from json file to Neo4j database')
            raise
