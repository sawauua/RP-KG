from rdflib import Graph, Namespace, RDF, URIRef, Literal, OWL
from rdflib.namespace import RDFS
from SPARQLWrapper import SPARQLWrapper, JSON
import time, re
import os
import requests


RPO = Namespace("http://www.semanticweb.org/ftsdemo/ontologies/2025/5/rpo#")

City         = RPO.City
Country      = RPO.Country
Continent    = RPO.Continent
Geographical = RPO.Geographical

MISCLASS = {RPO.Company, OWL.Thing, RPO.Thing, RPO.Resource, RPO.Organisation}

# Wikidata QIDs for fast checks
Q_CITY      = "Q515"
Q_COUNTRY   = "Q6256"
Q_CONTINENT = "Q5107"

### Wikidata helper #############################################

WD_ENDPOINT = "https://query.wikidata.org/sparql"
wd = SPARQLWrapper(WD_ENDPOINT, agent="kg-cleaner/0.1")
DBPEDIA_SPARQL = "https://dbpedia.org/sparql"
HEADERS = {"User-Agent": "ontology-lookup/0.1"}

def get_dbpedia_location(entity_name):

    uri = (
        "http://dbpedia.org/resource/"
        + entity_name.replace(" ", "_")
                      .replace("-", "_")
                      .replace(".", "")
                      .replace(",", "")
    )

    query = f"""
    PREFIX dbo:  <http://dbpedia.org/ontology/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX dbp: <http://dbpedia.org/property/>

    SELECT DISTINCT ?city ?country ?cont WHERE {{
      OPTIONAL {{
        <{uri}> dbo:location|dbo:headquarter|dbo:locationCity|dbp:city ?city .
      }}
      OPTIONAL {{
        <{uri}> dbp:country|dbo:country ?country .
      }}
      OPTIONAL {{
        ?country dbp:continent|dbo:continent ?cont .
      }}
    }}
    LIMIT 1
    """
    #time.sleep(0.8)
    try:
        res = requests.get(
            DBPEDIA_SPARQL,
            params={"query": query, "format": "json"},
            headers=HEADERS,
            timeout=15,
        )
        res.raise_for_status()
        bindings = res.json()["results"]["bindings"]
        if not bindings:
            return {"city": None, "country": None}

        row = bindings[0]
        #print(row)
        city    = row["city"]["value"]    if "city"    in row else None
        country = row["country"]["value"] if "country" in row else None
        continent = row["continent"]["value"] if "continent" in row else None
        return {"city": city, "country": country, "continent": continent}

    except requests.exceptions.RequestException as e:
        #print(f"DBpedia location lookup failed for '{entity_name}': {e}")
        return {"city": None, "country": None, "continent": None}

def ask_wikidata(query, return_ask = False):
    wd.setQuery(query)
    wd.setReturnFormat(JSON)
    result = wd.query().convert()

    if return_ask:
        return result.get("boolean", False)
    return result.get("results", {}).get("bindings", [])

def label_lookup(label):
    q = f'SELECT ?e WHERE {{ ?e rdfs:label "{label}"@en. }} LIMIT 1'
    rows = ask_wikidata(q)
    return rows[0]["e"]["value"].split("/")[-1] if rows else None

def geo_type(qid):
    q = f"""
    ASK {{ wd:{qid} wdt:P31/wdt:P279* wd:{Q_CITY} }}"""
    if ask_wikidata(q, return_ask = True):
        return "City"
    q = f"""
    ASK {{ wd:{qid} wdt:P31/wdt:P279* wd:{Q_COUNTRY} }}"""
    if ask_wikidata(q, return_ask = True):
        return "Country"
    q = f"""
    ASK {{ wd:{qid} wdt:P31/wdt:P279* wd:{Q_CONTINENT} }}"""
    if ask_wikidata(q, return_ask = True):
        return "Continent"
    return None

def get_location_chain(qid):
    q = f"""
    SELECT ?cityL ?countryL ?contL WHERE {{
      OPTIONAL {{ wd:{qid} wdt:P1376|wdt:P276|wdt:P131* ?city .
                 ?city wdt:P31/wdt:P279* wd:{Q_CITY} .
                 ?city rdfs:label ?cityL FILTER (LANG(?cityL)="en") }}
      OPTIONAL {{ wd:{qid} (wdt:P17|wdt:P131*) ?country .
                 ?country wdt:P31/wdt:P279* wd:{Q_COUNTRY} .
                 ?country rdfs:label ?countryL FILTER (LANG(?countryL)="en") }}
      OPTIONAL {{
        VALUES ?loc {{ wd:{qid} ?country ?city }}
        ?loc (wdt:P30|^wdt:P30) ?cont .
        ?cont wdt:P31/wdt:P279* wd:{Q_CONTINENT} .
        ?cont rdfs:label ?contL FILTER (LANG(?contL)="en")
      }}
    }} LIMIT 1"""
    rows = ask_wikidata(q)
    if not rows:
        return (None, None, None)
    row = rows[0]
    return (
        row.get("cityL", {}).get("value"),
        row.get("countryL", {}).get("value"),
        row.get("contL", {}).get("value"),
    )

# fix misclass

def makeName(string):
    string = string.replace('&', 'and')
    words = re.findall(r'\b[A-Za-z0-9]+\b', string)
    result = []
    for word in words:
        if word.isupper():
            result.append(word)
        else:
            result.append(word.capitalize())

    return ''.join(result)

def fix_geo_misclassifications(g: Graph) -> None:

    for subj in list(g.subjects(RDF.type, None)):
        old_types = set(g.objects(subj, RDF.type))
        if not (old_types & MISCLASS):
            continue  # not misclassified candidate

        label = str(subj).rsplit('#', 1)[-1].rsplit('/', 1)[-1]
        label = re.sub(r'(?<!^)(?=[A-Z])', ' ', label)
        
        qid = label_lookup(str(label))
        #print("label", label, "qid", qid)
        if not qid:
            continue

        geo = geo_type(qid)
        #print("geo:", geo)
        if not geo:
            results = get_dbpedia_location(label)
            #print(results)
            if results.get("city") is not None:
                g.add((subj, RPO.located_in, URIRef(f'{results.get("city")}')))
                g.add((URIRef(f'{results.get("city")}'), RDF.type, RPO.City))
                print("added city to", subj)
            if results.get("country") is not None:
                g.add((subj, RPO.located_in, URIRef(f'{results.get("country")}')))
                g.add((URIRef(f'{results.get("country")}'), RDF.type, RPO.Country))
                if results.get("city") is not None:
                    g.add((URIRef(f'{results.get("city")}'), RPO.located_in, URIRef(f'{results.get("country")}')))
            if results.get("continent") is not None:
                g.add((subj, RPO.located_in, results.get("continent")))
                g.add((URIRef(f'{results.get("city")}'), RDF.type, RPO.Continent))
                if results.get("city") is not None:
                    g.add((URIRef(f'{results.get("city")}'), RPO.located_in, URIRef(f'{results.get("continent")}')))
                    if results.get("country") is not None:
                        g.add((URIRef(f'{results.get("country")}'), RPO.located_in, URIRef(f'{results.get("continent")}')))
                
                print("Added cont to", subj)
            continue

        # upate graph
        for ot in old_types & MISCLASS:
            g.remove((subj, RDF.type, ot))

        new_cls = {"City": City, "Country": Country, "Continent": Continent}[geo]
        g.add((subj, RDF.type, new_cls))
        print(f"Re‑typed {label} -> {geo}")

        add_location_triples(g, [subj])

        time.sleep(0.2)  

#add location triples

LOC_CITY      = RPO.located_in
LOC_COUNTRY   = RPO.located_in
LOC_CONTINENT = RPO.located_in

def add_location_triples(g, subjects):
    for subj in subjects:
        label = g.value(subj, RDFS.label)
        if not label:
            continue
        qid = label_lookup(str(label))
        if not qid:
            continue
        city, country, cont = get_location_chain(qid)

        if city:
            city_uri = RPO[re.sub(r'\\W+', '_', city)]
            g.add((subj, LOC_CITY, city_uri))
            g.add((city_uri, RDFS.label, Literal(city)))
            g.add((city_uri, RDF.type, City))
            print("added stuff about city for ", subj)

        if country:
            country_uri = RPO[re.sub(r'\\W+', '_', country)]
            g.add((subj, LOC_COUNTRY, country_uri))
            g.add((country_uri, RDFS.label, Literal(country)))
            g.add((country_uri, RDF.type, Country))
            print("added stuff about country for ", subj)

        if cont:
            cont_uri = RPO[re.sub(r'\\W+', '_', cont)]
            g.add((subj, LOC_CONTINENT, cont_uri))
            g.add((cont_uri, RDFS.label, Literal(cont)))
            g.add((cont_uri, RDF.type, Continent))
            print("added stuff about continent for ", subj)

        time.sleep(0.2) 


g = Graph()
g.parse("merged_graph_with_sameAs.ttl", format="turtle")
fix_geo_misclassifications(g)
g.serialize("cleaned_geo.ttl", format="turtle")

from collections import defaultdict
from rdflib.namespace import OWL

def normalize_local_name(uri):

    if '#' in uri:
        local = uri.split('#')[-1]
    else:
        local = uri.split('/')[-1]
    return re.sub(r'[^a-zA-Z0-9]', '', local).lower()

def add_same_as_links_for_duplicates(g: Graph):

    seen = defaultdict(list)

    # Collect URIs by their normalized form
    for s in g.objects():
        if isinstance(s, URIRef):
            print("instance is uriref")
            norm = normalize_local_name(str(s))
            seen[norm].append(s)

    # Add owl:sameAs links for all duplicates
    for norm, uris in seen.items():
        if len(uris) > 1:
            print("len uris is ok")
            base = uris[0]
            for duplicate in uris[1:]:
                if (base != duplicate):
                    g.add((duplicate, OWL.sameAs, base))
                    print(f"Linked {duplicate} owl:sameAs {base}")

    return g


#file_path = r"C:/Users/FTS Demo/Documents/VU/3y/THESIS/final_code/merged_graph_with_sameAs.ttl"

#g = Graph()
#with open(file_path, "r", encoding="utf-8") as f:
#    g.parse(f, format="turtle")

#g = add_same_as_links_for_duplicates(g)

#g.serialize("deduplicated_kg.ttl", format="turtle")"""



