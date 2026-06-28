import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from app.core.config import get_settings
from app.providers.base import ProviderResponse


class SECEdgarClient:
    base_url = "https://data.sec.gov"

    def __init__(self) -> None:
        self.settings = get_settings()
        self.headers = {
            "User-Agent": self.settings.sec_user_agent,
            "Accept-Encoding": "gzip, deflate",
        }

    async def _get_json(self, url: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.settings.provider_timeout_seconds) as client:
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()

    async def _get_text(self, url: str) -> str:
        async with httpx.AsyncClient(timeout=self.settings.provider_timeout_seconds) as client:
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
            return response.text

    async def _post_json(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        headers = {**self.headers, "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=self.settings.provider_timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    async def company_search(self, company_name: str) -> ProviderResponse:
        encoded = quote_plus(company_name)
        url = (
            "https://www.sec.gov/cgi-bin/browse-edgar"
            f"?action=getcompany&company={encoded}&owner=exclude&output=atom&count=40"
        )
        try:
            text = await self._get_text(url)
            return ProviderResponse(
                provider="sec_edgar",
                data={"results": parse_company_search_atom(text)},
                source_url=url,
            )
        except Exception as exc:
            return ProviderResponse(
                provider="sec_edgar",
                data={"results": []},
                source_url=url,
                error=str(exc),
            )

    async def company_tickers(self) -> ProviderResponse:
        url = "https://www.sec.gov/files/company_tickers.json"
        try:
            data = await self._get_json(url)
            return ProviderResponse(provider="sec_edgar", data=data, source_url=url)
        except Exception as exc:
            return ProviderResponse(provider="sec_edgar", data={}, source_url=url, error=str(exc))

    async def find_cik(self, company_name: str) -> ProviderResponse:
        tickers = await self.company_tickers()
        if tickers.error:
            return tickers
        needle = company_name.lower()
        for row in tickers.data.values():
            title = str(row.get("title", "")).lower()
            if needle in title:
                cik = str(row.get("cik_str", "")).zfill(10)
                return ProviderResponse(
                    provider="sec_edgar",
                    data={"cik": cik, "ticker": row.get("ticker"), "title": row.get("title")},
                    source_url=tickers.source_url,
                )
        return ProviderResponse(
            provider="sec_edgar",
            data={"cik": None, "ticker": None, "title": None},
            source_url=tickers.source_url,
        )

    async def full_text_search(
        self,
        query: str,
        forms: Optional[List[str]] = None,
        start: int = 0,
        size: int = 10,
    ) -> ProviderResponse:
        url = "https://efts.sec.gov/LATEST/search-index"
        payload = {
            "q": query,
            "forms": forms or [],
            "from": start,
            "size": min(size, 100),
        }
        try:
            data = await self._post_json(url, payload)
            return ProviderResponse(provider="sec_edgar", data=data, source_url=url)
        except Exception as exc:
            return ProviderResponse(provider="sec_edgar", data={}, source_url=url, error=str(exc))

    async def submissions(self, cik: str) -> ProviderResponse:
        normalized = str(cik).zfill(10)
        url = f"{self.base_url}/submissions/CIK{normalized}.json"
        try:
            data = await self._get_json(url)
            return ProviderResponse(provider="sec_edgar", data=data, source_url=url)
        except Exception as exc:
            return ProviderResponse(provider="sec_edgar", data={}, source_url=url, error=str(exc))

    async def company_facts(self, cik: str) -> ProviderResponse:
        normalized = str(cik).zfill(10)
        url = f"{self.base_url}/api/xbrl/companyfacts/CIK{normalized}.json"
        try:
            data = await self._get_json(url)
            return ProviderResponse(provider="sec_edgar", data=data, source_url=url)
        except Exception as exc:
            return ProviderResponse(provider="sec_edgar", data={}, source_url=url, error=str(exc))

    async def latest_filings_by_form(self, cik: str, form: str) -> ProviderResponse:
        submissions = await self.submissions(cik)
        if submissions.error:
            return submissions
        recent = submissions.data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        matches = []
        for index, current_form in enumerate(forms):
            if str(current_form).upper() == form.upper():
                matches.append(
                    {
                        "form": current_form,
                        "filing_date": recent.get("filingDate", [None])[index],
                        "accession_number": recent.get("accessionNumber", [None])[index],
                        "primary_document": recent.get("primaryDocument", [None])[index],
                    }
                )
        return ProviderResponse(
            provider="sec_edgar",
            data={"cik": cik, "form": form, "filings": matches},
            source_url=submissions.source_url,
        )


sec_edgar_client = SECEdgarClient()


def parse_company_search_atom(text: str) -> List[Dict[str, Optional[str]]]:
    if not text.strip():
        return []

    def local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []

    results: List[Dict[str, Optional[str]]] = []
    for entry in root.iter():
        if local_name(entry.tag) != "entry":
            continue
        title = None
        cik = None
        href = None
        for child in entry.iter():
            name = local_name(child.tag)
            if name == "title" and child.text and not title:
                title = child.text.strip()
            if name == "cik" and child.text and not cik:
                cik = child.text.strip().zfill(10)
            if name == "link" and not href:
                href = child.attrib.get("href")
        if title or cik:
            results.append({"title": title, "cik": cik, "url": href})
    return results
