from rdflib import Graph, RDF, OWL, URIRef

# List of ontology file paths (adjust these to your actual paths)
ontology_files = [
    r"C:\Users\FTS Demo\Documents\VU\3y\THESIS\final_code\rpkg_full.ttl",
    r"C:\Users\FTS Demo\Documents\VU\3y\THESIS\final_code\all_papers_entities.ttl",
    r"C:\Users\FTS Demo\Documents\VU\3y\THESIS\final_code\research-power-ontology.rdf"
]

# Final merged graph
merged_graph = Graph()

idx = 0

def squash_double_hash(uri: URIRef) -> URIRef:
    s = str(uri)
    if s.count("#") <= 1:
        return uri                         # nothing to fix
    head, tail = s.split("#", 1)           # first “#”
    tail = tail.replace("#", "")           # drop all later “#”
    return URIRef(f"{head}#{tail}")

# Parse and merge each ontology
for file_path in ontology_files:
    idx+=1
    print(f"Parsing: {file_path}")
    g = Graph()
    if "ttl" in file_path:
        g.parse(file_path, format="turtle")  
    elif "rdf" in file_path:
        g.parse(file_path, format="xml")
        
    for s, p, o in g.triples((None, RDF.type, OWL.Ontology)):
        print(f"Original ontology iri: {s}")
        g.remove((s, RDF.type, OWL.Ontology))
        # Create a new unique ontology URI
        new_iri = URIRef(f"http://www.semanticweb.org/ftsdemo/ontologies/2025/5/rpo{idx}#")
        print(f"Replacing with new iri: {new_iri}")
        g.add((new_iri, RDF.type, OWL.Ontology))
        break  # assume one ontology per file
        
    for s, p, o in list(g):  # list() so we can modify in‑place safely
        s2 = squash_double_hash(s) if isinstance(s, URIRef) else s
        p2 = squash_double_hash(p) if isinstance(p, URIRef) else p
        o2 = squash_double_hash(o) if isinstance(o, URIRef) else o
        if (s, p, o) != (s2, p2, o2):
            g.remove((s, p, o))
            g.add((s2, p2, o2))

    merged_graph += g

print(f"Total triples in merged graph: {len(merged_graph)}")

# Optional: save to a new file
merged_graph.serialize(destination=r"C:\Users\FTS Demo\Documents\VU\3y\THESIS\final_code\merged.ttl", format="turtle")

