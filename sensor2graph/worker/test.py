from .util.pcd_util import pick_seed_point
import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()


NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")


def test_graph_query(driver):
    element_id = input("Enter the element ID to query: ").strip()

    with driver.session() as session:
        result = session.run(
            "MATCH (w:Wall {id: $element_id}) "
            "RETURN w.id AS id, w.name AS name, w.layerCount AS layerCount",
            element_id=element_id,
        )
        rows = list(result)
        if not rows:
            print("No wall found.")
            return

        for row in rows:
            print(
                # row["id"],
                # row["name"],
                row["layerCount"]
            )


if __name__ == "__main__":
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    test_graph_query(driver)
    driver.close()
    pick_seed_point("cloudGlobal_cleaned.pcd", None)
