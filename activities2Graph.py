import synapseclient
import load2Neo4jDB as ndb
import multiprocessing.dummy as mp
import threading
import argparse
import logging
import json
from collections import OrderedDict
from py2neo import Graph, authenticate

syn = synapseclient.login()

NODETYPES = {0:'dataset',1: 'layer',2: 'project',3: 'preview',4: 'folder',
             5: 'analysis',6: 'step', 7: 'code',8: 'link',9: 'phenotypedata',
             10:'genotypedata',11:'expressiondata',12:'robject',
             13:'summary',14:'genomicdata',15:'page',16:'file',17:'table',
             18:'community'} #used in getEntities

class threadsafe_iter:
    """Takes an iterator/generator and makes it thread-safe by
    serializing call to the `next` method of given iterator/generator.
    """
    def __init__(self, it):
        self.it = it
        self.lock = threading.Lock()

    def __iter__(self):
        return self

    def next(self):
        with self.lock:
            return self.it.next()

def threadsafe_generator(f):
    """A decorator that takes a generator function and makes it thread-safe.
    """
    def g(*a, **kw):
        return threadsafe_iter(f(*a, **kw))
    return g

@threadsafe_generator
def idGenerator(start=0):
    '''generates relevant id numbers starting from 0 as default'''
    i = start
    while True:
        yield i
        i +=1;

newId = idGenerator()#29602)
counter2 = idGenerator()

def getEntities(projectId):
    '''get and format all entities with the inputted projectId'''
    logging.info('Getting and formatting all entities with the inputted projectId')
    query = syn.chunkedQuery('select * from entity where projectId =="%s"' %projectId)
    entityDict = dict()
    for ent in query:
        if ent['entity.nodeType'] in [2,3,4]: 
	#Remove containers by ignoring layers, projects, and previews
            continue
        for key in ent.keys():
            #remove the "entity" portion of query
            new_key = '.'.join(key.split('.')[1:])
            item = ent.pop(key)
            ent[new_key] = item[0] if (type(item) is list and len(item)>0) else item
        ent['_type']='vertex'
        ent['_id'] = newId.next()
        ent['synId'] = ent.pop('id')

        versionNumber = ent['versionNumber']
        entityDict['%s.%s' %(ent['synId'],versionNumber)] = ent 
        logging.info('Getting entity (%i): %s.%s' %(ent['_id'], ent['synId'],
                                             ent['versionNumber']))
        #retrieve previous versions
        if int(versionNumber) > 1:
            for version in range(1,int(versionNumber)):
                ent['_id'] = newId.next()
                entityDict['%s.%s' %(ent['synId'],version)] = ent 
                logging.info('Getting previous version of entity (%i): %s.%i' %(ent['_id'],
                                             ent['synId'], version))
    return entityDict

def safeGetActivity(entity):
    '''retrieve activity/provenance associated with a particular entity'''
    k, ent = entity
    try:
        print 'Getting Provenance for:', k, counter2.next()
        prov = syn.getProvenance(ent['synId'], version=ent['versionNumber'])
        return (k, prov)
    except synapseclient.exceptions.SynapseHTTPError:
        return (k, None)

def cleanUpActivities(activities):
    '''remove all activity-less entities'''
    logging.info('Removing all activity-less entities')
    returnDict = dict()
    for k,activity in activities:
        logging.info('Cleaning up activity: %s' % k)
        if activity is None:
            continue
        activity['synId'] = activity.pop('id')
        activity['concreteType']='activity'
        activity['_id'] = newId.next()
        activity['_type'] = 'vertex'
        returnDict[k] = activity
    return returnDict
    
def buildEdgesfromActivities(nodes, activities):
    '''construct directed edges based on provenance'''
    logging.info('Constructing directed edges based on provenance')
    new_nodes = dict()
    edges = list()
    for k, entity in nodes.items():
        logging.info('processing entity:', k)
        if k not in activities:
            continue
        activity = activities[k]
        #Determine if we have already seen this activity
        if activity['synId'] not in new_nodes:
            new_nodes[activity['synId']]  = activity
            #Add input relationships
            for used in activity['used']:
                edges = addNodesandEdges(used, nodes, activity, edges)
        else:
            activity = new_nodes[activity['synId']]
        #Add generated relationship (i.e. out edge)
        edges.append({'_id': newId.next(),
                      '_inV': entity['_id'],
                      '_outV': activity['_id'],
                      '_type':'edge', '_label':'generatedBy',
                      'createdBy': activity['createdBy'],
                      'createdOn': activity['createdOn'],
                      'modifiedBy':activity['modifiedBy'],
                      'modifiedOn':activity['modifiedOn']})
    nodes.update(new_nodes)
    return edges


def addNodesandEdges(used, nodes, activity, edges):
    #add missing vertices to nodes with edges
    if used['concreteType']=='org.sagebionetworks.repo.model.provenance.UsedEntity':
        targetId = '%s.%s' %(used['reference']['targetId'],
                             used['reference'].get('targetVersionNumber'))
        if targetId not in nodes:
            nodes[targetId] = { '_id': newId.next(),
                                '_type': 'vertex',
                                'synId' : used['reference']['targetId'],
                                'versionNumber': used['reference'].get('targetVersionNumber')}
    elif used['concreteType'] =='org.sagebionetworks.repo.model.provenance.UsedURL':
        targetId = used['url']
        if not targetId in nodes:
            nodes[targetId]= {'_id': newId.next(),
                              '_type': 'vertex',
                              'name': used.get('name'),
                              'url': used['url'],
                              'concreteType' : used['concreteType']}
    #Create the incoming edges
    edges.append({'_id': newId.next(),
                  '_inV': activity['_id'],
                  '_type': 'edge',
                  '_outV': nodes[targetId]['_id'],
                  '_label': 'used',
                  'wasExecuted': used.get('wasExecuted', False),
                  'createdBy': activity['createdBy'],
                  'createdOn': activity['createdOn'],
                  'modifiedBy':activity['modifiedBy'],
                  'modifiedOn':activity['modifiedOn']})

    return edges


if __name__ == '__main__':
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    parser = argparse.ArgumentParser(description=
                'Please input the [1] synapse ID or space-separated list of synapse ID and the [2] name of json outfile to graph provenance')
    parser.add_argument('id', metavar='synId', nargs='+', help='Input the synapse ID or list of synapse IDs')
    parser.add_argument('--j', metavar='json', help='Input name of json outfile')
    parser.add_argument('--p', type=int, help='Specify the pool size for the multiprocessing module')
    args = parser.parse_args()
    
    syn = synapseclient.Synapse()
    syn.login()

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
        nodes.update(getEntities(projectId = proj))
    logging.info('Fetched %i entities' %len(nodes))

    activities = p.map(safeGetActivity, nodes.items())
    activities = cleanUpActivities(activities)
    print '%i activities found i.e. %0.2g%% entities have provenance' %(len(activities), 
                                                                        float(len(nodes))/len(activities))
    edges = buildEdgesfromActivities(nodes, activities)
    logging.info('I have  %i nodes and %i edges' %(len(nodes), len(edges)))
    with open(json_file, 'w') as fp:
        json.dump(OrderedDict([('vertices', nodes.values()), ('edges', edges)]), fp, indent=4)

    logging.info('Connecting to Neo4j and authenticating user credentials')
    with open('credentials.json') as creds:
        db_info=json.load(creds)
    authenticate(db_info['machine'], db_info['username'], db_info['password'])
    db_dir = db_info['machine'] + "/db/data"
    graph = Graph(db_dir)

    try:
        nbd.json2neo4j(str(json_file), graph)
    except:
        logging.error('Error involving loading data from json file to Neo4j database')
        raise
