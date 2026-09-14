"""Deterministic checks for the cached V2 administrative catalog."""

import unittest

from app.services.v2.administrative import list_districts, list_states, search_places


class AdministrativeCatalogTests(unittest.TestCase):
    def test_state_search_is_data_driven(self) -> None:
        states = list_states("Telangana")
        self.assertEqual(len(states), 1)
        self.assertEqual(states[0]["name"], "Telangana")
        self.assertEqual(states[0]["level"], "state")
        self.assertEqual(len(states[0]["bbox"]), 4)

    def test_districts_are_scoped_to_state(self) -> None:
        states = list_states("Telangana")
        districts = list_districts(states[0]["id"])
        self.assertGreaterEqual(len(districts), 1)
        self.assertTrue(all(item["state_id"] == states[0]["id"] for item in districts))
        self.assertIn("Hyderabad", {item["name"] for item in districts})

    def test_search_returns_bounded_place_results(self) -> None:
        results = search_places("Hyderabad", limit=5)
        self.assertLessEqual(len(results), 5)
        self.assertEqual(results[0]["district_name"], "Hyderabad")


if __name__ == "__main__":
    unittest.main()
