import gc
import json
import csv
import pandas as pd
import sys
import os
from py2neo import Graph, authenticate

gc.collect()
# Connect to graph and add constraints.
print 'Connecting to Neo4j and authenticating user credentials'
authenticate("ec2-54-91-28-8.compute-1.amazonaws.com:7474", "neo4j", "sage2016")
graph = Graph("http://ec2-54-91-28-8.compute-1.amazonaws.com:7474/db/data")

def json2neo4j(jsonfilename):
    # Retrieve JSON/CSV file
    print 'Retrieving local JSON/CSV file'
    if not os.path.isfile('vertices.csv'):
        print 'Converting JSON to CSV'

        with open(jsonfilename) as json_file:
            JSON = json.load(json_file)

        df1 = pd.DataFrame(JSON['vertices'])
        df1 = df1.drop('used', 1)
        df1 = df1.drop('description', 1)
        df1.to_csv('vertices.csv', encoding='utf-8', index=False)

        df2 = pd.DataFrame(JSON['edges'])
        df2.to_csv('edges.csv', index=False) 
        # index=False removes first column with null header

    # Add uniqueness constraints and indexing
    print 'Establishing uniqueness constraints and indexing'
    graph.run("CREATE CONSTRAINT ON (entity:Entity) ASSERT entity.id IS UNIQUE")
    graph.run("CREATE CONSTRAINT ON (activity:Activity) ASSERT activity.id IS UNIQUE")
    graph.run("CREATE INDEX ON :Entity(entity)")


    # Build query
    aQuery = """
    USING PERIODIC COMMIT 1000
    LOAD CSV WITH HEADERS FROM "file:///vertices.csv" AS dvs
    WITH dvs WHERE NOT dvs.concreteType = "activity"
       MERGE (entity:Entity {id:dvs._id}) ON CREATE
       SET entity = dvs
    """
    bQuery = """
    USING PERIODIC COMMIT 1000
    LOAD CSV WITH HEADERS FROM "file:///vertices.csv" AS dvs
    WITH dvs WHERE dvs.concreteType = "activity"
       MERGE (activity:Activity {id:dvs._id}) ON CREATE 
       SET activity = dvs
    """
    cQuery = """
    USING PERIODIC COMMIT 1000
    LOAD CSV WITH HEADERS FROM "file:///edges.csv" AS erow
    MATCH (in_node:Entity { _id:erow._inV })
    MATCH (out_node:Activity { _id:erow._outV })
    MERGE (out_node)-[:GENERATED_BY { action:erow._label, id:erow._id }]->(in_node)
    """
    dQuery = """
    USING PERIODIC COMMIT 1000
    LOAD CSV WITH HEADERS FROM "file:///edges.csv" AS erow
    MATCH (in_node:Activity { _id:erow._inV })
    MATCH (out_node:Entity { _id:erow._outV })
    MERGE (out_node)-[:USED { action:erow._label, id:erow._id }]->(in_node)
    """

    # Send Cypher query
    print 'Loading data from CSV file(s) to Neo4j'
    graph.run(aQuery)
    graph.run(bQuery)
    graph.run(cQuery)
    graph.run(dQuery)
    graph.run("DROP CONSTRAINT ON (entity:Entity) ASSERT entity.id IS UNIQUE")
    graph.run("DROP CONSTRAINT ON (activity:Activity) ASSERT activity.id IS UNIQUE")
    graph.run("MATCH (n) WHERE n:Activity OR n:Entity REMOVE n.id").evaluate()
    print 'Done.'

    # Clean up directory and remove created files
    # Comment out if you would like to keep csv files
    print 'Removing csv files from local directory'
    os.chmod('vertices.csv', stat.S_IWGRP)
    os.chmod('edges.csv', stat.S_IWGRP)
    dir_info = os.stat('~')
    uid = dir_info.st_uid
    gid = dir_info.st_gid
    os.chown(nodes.name, uid, gid)
    os.chown(edges.name, uid, gid)
    os.remove('vertices.csv')
    os.remove('edges.csv')

if __name__ == '__main__':
    print('Please input the [1] synapse ID [2] name of json outfile to graph provenance')

    if len(sys.argv) != 2:
        print 'Incorrect number of arguments'
        sys.exit(1)
    else:
        jsonfile = str(sys.argv[1])
        try:
            json2neo4j(jsonfile)
        except:
            print 'Error involving loading data from json file to Neo4j database'
            raise
