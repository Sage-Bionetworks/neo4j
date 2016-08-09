# Neo4j

### Useful Cypher queries for Neo4j Database

Return a list with the name of all activities
MATCH (n:Activity) RETURN n.name

Return a list with the name of all entities
MATCH (n:Entity) RETURN n.name

Return a count of all activities
MATCH (n:Activity) RETURN count(n)

Return a count of all activities
MATCH (n:Entity) RETURN count(n)

Return ratio of activities to entity
MATCH (n:Activity) WITH toFloat(count(n)) as num MATCH (m:Entity) RETURN num/count(m)

Use known annotation/property value to find a particular node
MATCH (n {annotationName:"VALUE"}) RETURN n
or
MATCH (n) WHERE annotationName = "VALUE" RETURN n

Example - display all activities, entities, and their relationships stemming from a given user
MATCH p = (n {createdBy: "#######"})<-[*]-(m) RETURN DISTINCT p, collect(m)

More detailed examples:

Return a list of synIds for every file derived from PCBC protocols not involving Aravind Ramakrishnan as the originating scientist that possess the particular annotation "Diffname_short"
MATCH (protocol {fileType:"protocol", projectId:"1773109.0"}) WHERE NOT protocol.Originating_Scientist = "Aravind Ramakrishnan" AND EXISTS(protocol.Diffname_short) WITH collect(protocol) as prots
UNWIND prots as prot
   MATCH (n {synId:prot.synId})<-[*]-(m:Entity) WHERE NOT (m)<-[*]-() AND m.projectId = m.benefactorId AND exists(m.Originating_Lab)
   RETURN n.synId AS parent_id, count(distinct m.synId) AS derived_files

Return a list of all files within PsychEncode which similarly used BWA alignment tool downloaded from SourceForge, ordered alphanumerically by their synId 
MATCH (n {projectId:"4921369.0", fileType:"bam"})-[r]-(s)-[t]->(m {name:"http://sourceforge.net/projects/bio-bwa/files/bwa-0.6.2.tar.bz2/download"}) RETURN DISTINCT n.name, n.synId AS synId ORDER BY synId DESC
