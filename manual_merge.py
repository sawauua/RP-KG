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

# Parse and merge each ontology
for file_path in ontology_files:
    idx+=1
    print(f"Parsing: {file_path}")
    g = Graph()
    if "ttl" in file_path:
        g.parse(file_path, format="turtle")  # Change format if needed (e.g., "xml", "n3")
    elif "rdf" in file_path:
        g.parse(file_path, format="xml")
        
    for s, p, o in g.triples((None, RDF.type, OWL.Ontology)):
        print(f"Original ontology IRI: {s}")
        g.remove((s, RDF.type, OWL.Ontology))
        # Create a new unique ontology URI
        new_iri = URIRef(f"http://www.semanticweb.org/ftsdemo/ontologies/2025/5/rpo{idx}#")
        print(f"Replacing with new IRI: {new_iri}")
        g.add((new_iri, RDF.type, OWL.Ontology))
        break  # assume one ontology per file

    merged_graph += g

print(f"Total triples in merged graph: {len(merged_graph)}")

# Optional: save to a new file
merged_graph.serialize(destination=r"C:\Users\FTS Demo\Documents\VU\3y\THESIS\final_code\merged.rdf", format="xml")

