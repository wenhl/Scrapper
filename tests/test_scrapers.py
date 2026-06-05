import unittest

from scrapers import nationwide, progressive


class ProgressiveParserTests(unittest.TestCase):
    def test_classifies_progressive_urls(self):
        self.assertEqual(
            progressive.classify_url(["local-agent", "pennsylvania", "apollo"]),
            "city",
        )
        self.assertEqual(
            progressive.classify_url(["local-agent", "pennsylvania", "apollo", "agency"]),
            "agency",
        )

    def test_parses_progressive_city_links(self):
        html = """
        <ul class="city-list">
          <li><a href="https://www.progressiveagent.com/local-agent/pennsylvania/apollo/">Apollo</a></li>
        </ul>
        """
        self.assertEqual(
            progressive.parse_state_city_links(html),
            ["https://www.progressiveagent.com/local-agent/pennsylvania/apollo/"],
        )

    def test_extracts_progressive_agent_data(self):
        agent_json = {
            "name": "Example Agency",
            "address": {
                "streetAddress": "1 Main St",
                "addressLocality": "Apollo",
                "addressRegion": "PA",
                "postalCode": "15613",
            },
            "email": "INFO@EXAMPLE.COM",
            "telephone": "(555) 123-4567",
            "knowsLanguage": "English",
            "url": "https://example.com",
            "@id": "https://www.progressiveagent.com/local-agent/pennsylvania/apollo/example/",
        }
        self.assertEqual(
            progressive.extract_agent_data(agent_json),
            {
                "AgencyName": "Example Agency",
                "StreetAddress": "1 Main St",
                "City": "Apollo",
                "State": "PA",
                "PostalCode": "15613",
                "Email": "info@example.com",
                "Phone": "(555) 123-4567",
                "Language": "English",
                "Website": "https://example.com",
                "Link": "https://www.progressiveagent.com/local-agent/pennsylvania/apollo/example/",
            },
        )


class NationwideParserTests(unittest.TestCase):
    def test_classifies_nationwide_urls(self):
        self.assertEqual(nationwide.classify_url(["pa", "apollo"]), "city")
        self.assertEqual(
            nationwide.classify_url(["pa", "apollo", "15613", "agency"]),
            "agency",
        )

    def test_parses_nationwide_state_and_city_links(self):
        base_html = """
        <a href="/pa">Pennsylvania</a>
        <a href="/ca">California</a>
        <a href="/la/metairie">Louisiana</a>
        <a href="/ok/tulsa">Oklahoma</a>
        <a href="/dc/washington">Washington DC</a>
        <a href="/auto">Auto</a>
        <a href="https://www.nationwide.com/">Nationwide</a>
        """
        state_html = """
        <a href="/pa/apollo">Apollo</a>
        <a href="https://agency.nationwide.com/pa/pittsburgh">Pittsburgh</a>
        <a href="/oh/akron">Akron</a>
        """
        self.assertEqual(
            nationwide.parse_state_links(base_html),
            ["ca", "dc", "la", "ok", "pa"],
        )
        self.assertEqual(
            nationwide.parse_state_city_links(state_html, "pa"),
            [
                "https://agency.nationwide.com/pa/apollo",
                "https://agency.nationwide.com/pa/pittsburgh",
            ],
        )

    def test_extracts_nationwide_json_ld_agent_data(self):
        html = """
        <script type="application/ld+json">
        {
          "@type": "InsuranceAgency",
          "name": "Example Nationwide Agency",
          "telephone": "(555) 123-4567",
          "email": "INFO@EXAMPLE.COM",
          "url": "https://agency.example.com",
          "@id": "https://agency.nationwide.com/pa/apollo/example",
          "address": {
            "streetAddress": "1 Main St",
            "addressLocality": "Apollo",
            "addressRegion": "PA",
            "postalCode": "15613"
          }
        }
        </script>
        <a href="mailto:INFO@EXAMPLE.COM">Email</a>
        <a href="https://www.example-agency.com/">https://www.example-agency.com/</a>
        <h3>Insurable Products</h3>
        <ul><li>Auto</li><li>Commercial</li><li>Home</li></ul>
        """
        agent_json = nationwide.first_agency_json(html)
        offer_info = nationwide.extract_products(html)
        self.assertEqual(
            nationwide.extract_agent_data_from_json(
                agent_json,
                "https://agency.nationwide.com/pa/apollo/example",
                offer_info,
                "English",
            ),
            {
                "Commercial": "Y",
                "AgencyName": "Example Nationwide Agency",
                "StreetAddress": "1 Main St",
                "City": "Apollo",
                "State": "PA",
                "PostalCode": "15613",
                "Email": "info@example.com",
                "Phone": "(555) 123-4567",
                "Language": "English",
                "Website": "https://agency.example.com",
                "Link": "https://agency.nationwide.com/pa/apollo/example",
                "Offer": "Auto, Commercial, Home",
            },
        )

    def test_extracts_nationwide_contact_links(self):
        html = """
        <a href="https://agency.nationwide.com">Nationwide</a>
        <a href="mailto:INFO@EXAMPLE.COM?subject=Quote">Email</a>
        <a href="https://www.example-agency.com/">https://www.example-agency.com/</a>
        <a href="https://www.facebook.com/example">Facebook</a>
        """
        self.assertEqual(
            nationwide.extract_contact_links(html),
            ("INFO@EXAMPLE.COM", "https://www.example-agency.com/"),
        )

    def test_extracts_scoped_nationwide_products_and_languages(self):
        html = """
        <nav>
          <a>Business auto</a>
          <a>Business property</a>
          <a>Commercial agribusiness</a>
        </nav>
        <ul>
          <li class="Core-product">Auto</li>
          <li class="Core-product">Commercial</li>
          <li class="Core-product">Home</li>
        </ul>
        <div class="AgentAbout-section">
          <h3 class="AgentAbout-sectionTitle">Languages Spoken</h3>
          <ul>
            <li class="AgentAbout-sectionListItem">English</li>
            <li class="AgentAbout-sectionListItem">Spanish</li>
          </ul>
        </div>
        """
        self.assertEqual(nationwide.extract_products(html), "Auto, Commercial, Home")
        self.assertEqual(nationwide.extract_languages(html), "English, Spanish")


if __name__ == "__main__":
    unittest.main()
