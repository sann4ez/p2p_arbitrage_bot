import unittest

from services.p2p_recommendation_ai import extract_url_citations


class ExtractUrlCitationsTests(unittest.TestCase):
    def test_accepts_nullable_openai_collections(self):
        response = {"output": None, "choices": None}

        self.assertEqual(extract_url_citations(response), [])

    def test_skips_nullable_nested_collections(self):
        response = {
            "output": [
                {"action": {"sources": None}, "content": None},
                {"content": [{"annotations": None}]},
            ],
            "choices": [{"message": None}],
        }

        self.assertEqual(extract_url_citations(response), [])

    def test_extracts_citations_while_ignoring_nulls(self):
        response = {
            "output": [
                None,
                {
                    "action": {
                        "sources": [
                            None,
                            {"title": "NBU", "url": "https://bank.gov.ua/"},
                        ]
                    },
                    "content": [
                        {
                            "annotations": [
                                None,
                                {
                                    "url_citation": {
                                        "title": "OpenAI",
                                        "url": "https://openai.com/",
                                    }
                                },
                            ]
                        }
                    ],
                },
            ]
        }

        self.assertEqual(
            extract_url_citations(response),
            [
                {"title": "NBU", "url": "https://bank.gov.ua/"},
                {"title": "OpenAI", "url": "https://openai.com/"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
