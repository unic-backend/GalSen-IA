"""
Lire ce qu'un document dit de lui-même — sans le croire sur parole (ADR-021, étape 6).

Un PDF porte un titre, une date, un auteur ; une page HTML porte ses `<meta>` et
son Dublin Core. C'est la seule source de métadonnées qui existe pour un document
récupéré, et elle vient **de l'extérieur** : elle se lit comme une donnée, jamais
comme une autorité.

## Deux règles, et la seconde est celle qui compte

1. **Ce qui n'est pas trouvé vaut `unknown`.** Jamais une valeur plausible,
   jamais un repli sur autre chose.
2. **La date de publication n'est jamais déduite.** Pas de la date de
   récupération, pas de l'URL, pas du nom du fichier. Une date ambiguë
   (`03/04/2024` : mars ou avril ?) rend `unknown` **avec sa raison**, parce
   qu'un classement chronologique faux est invisible et durable.

## Ce que ce module n'établit pas

L'institution, le rang et le pays ne viennent **pas** d'ici : ils viennent du
registre. Un document qui se déclare « publication officielle du ministère » ne
gagne rien à le dire — c'est exactement la règle que le registre existe pour
tenir. Ce module ne remplit que ce que le document sait de lui-même : titre,
date, éditeur revendiqué, URL canonique.
"""

import re
from html import unescape
from typing import Any, Dict

#: Ce qui n'a pas été trouvé. `unknown` n'est pas « absent » : c'est une lacune
#: qui se transmet à toute réponse construite sur ce document.
INCONNU = "unknown"

_BALISE_META = re.compile(r"<meta\b[^>]*>", re.IGNORECASE)
_ATTRIBUT = re.compile(r"""(\w[\w.:-]*)\s*=\s*["']([^"']*)["']""")
_TITRE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_LIEN = re.compile(r"<link\b[^>]*>", re.IGNORECASE)

#: Noms de `<meta>` portant un titre, du plus spécifique au plus général.
NOMS_DE_TITRE = ("citation_title", "dc.title", "dcterms.title", "og:title", "title")

#: Noms portant une date de publication. `dc.date` est délibérément avant
#: `date` : le second peut être une date de mise à jour du gabarit.
NOMS_DE_DATE = (
    "citation_publication_date", "dc.date.issued", "dcterms.issued", "dc.date",
    "article:published_time", "datepublished", "date",
)

#: Noms portant l'éditeur **revendiqué**. Le registre, lui, dit l'institution.
NOMS_D_EDITEUR = ("citation_publisher", "dc.publisher", "dcterms.publisher", "og:site_name")

#: Noms portant la langue déclarée par le document.
NOMS_DE_LANGUE = ("dc.language", "dcterms.language", "og:locale", "language")

# `\b` ne suffit pas en fin de motif : dans « 2024-03-15T10:00 », le « 5 » et
# le « T » sont tous deux des caractères de mot, donc il n'y a pas de
# frontière — la date ISO passait inaperçue et seule l'année était lue.
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})(?![\d-])")
_ANNEE_SEULE = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")
_AMBIGUE = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b")


def _metas(html: str) -> Dict[str, str]:
    """Retourne les `<meta>` d'une page, indexées par nom en minuscules."""
    trouvees: Dict[str, str] = {}
    for balise in _BALISE_META.findall(html):
        attributs = {
            nom.lower(): valeur for nom, valeur in _ATTRIBUT.findall(balise)
        }
        cle = attributs.get("name") or attributs.get("property") or attributs.get("itemprop")
        contenu = attributs.get("content")
        if cle and contenu:
            trouvees.setdefault(cle.strip().lower(), unescape(contenu).strip())
    return trouvees


def _premier(metas: Dict[str, str], noms) -> str:
    """Retourne la première valeur trouvée parmi une liste de noms."""
    for nom in noms:
        valeur = metas.get(nom)
        if valeur:
            return valeur
    return ""


def normalize_date(valeur: str) -> Dict[str, str]:
    """
    Ramène une date à sa forme ISO, ou refuse de trancher.

    Une date ambiguë rend `unknown` **avec sa raison** : `03/04/2024` est mars
    pour un lecteur et avril pour un autre, et un classement chronologique faux
    ne se voit jamais.
    """
    texte = str(valeur or "").strip()
    if not texte:
        return {"date": INCONNU, "reason": "Aucune date déclarée par le document."}

    iso = _ISO.search(texte)
    if iso:
        return {"date": iso.group(0), "reason": "Date ISO déclarée."}

    ambigue = _AMBIGUE.search(texte)
    if ambigue:
        premier, second = int(ambigue.group(1)), int(ambigue.group(2))
        if premier > 12 or second > 12:
            jour, mois = (premier, second) if premier > 12 else (second, premier)
            return {
                "date": f"{ambigue.group(3)}-{mois:02d}-{jour:02d}",
                "reason": "Un des deux nombres dépasse 12 : l'ordre est levé.",
            }
        return {
            "date": INCONNU,
            "reason": (
                f"« {ambigue.group(0)} » est ambiguë : {premier} peut être le jour "
                f"ou le mois. Deviner produirait un classement chronologique faux, "
                "et un classement faux ne se voit pas."
            ),
        }

    annee = _ANNEE_SEULE.search(texte)
    if annee:
        return {
            "date": annee.group(0),
            "reason": "Seule l'année est déclarée ; le jour et le mois restent inconnus.",
        }

    return {"date": INCONNU, "reason": f"« {texte} » n'est pas une date lisible."}


def _langue_declaree(valeur: str) -> str:
    """
    Ramène une locale déclarée à son code de langue.

    `fr_FR`, `fr-FR` et `FR` désignent la même langue ; ce qui compte ici est la
    langue, pas la région. Tronquer bêtement à cinq caractères transformait la
    sentinelle `unknown` en « unkno », qui ressemblait alors à une déclaration —
    et tout document sans langue déclarée partait en quarantaine pour un
    désaccord avec une langue que personne n'avait déclarée.
    """
    texte = str(valeur or "").strip().lower()
    if not texte:
        return INCONNU
    return re.split(r"[-_]", texte)[0][:3]


def from_html(contenu: bytes, url: str = "") -> Dict[str, Any]:
    """
    Extrait les métadonnées d'une page.

    Returns:
        Les champs trouvés, ceux absents à `unknown`, et `date_reason` qui dit
        pourquoi une date manque quand elle manque.
    """
    html = contenu.decode("utf-8", errors="replace") if contenu else ""
    metas = _metas(html)

    titre = _premier(metas, NOMS_DE_TITRE)
    if not titre:
        balise = _TITRE.search(html)
        titre = unescape(balise.group(1)).strip() if balise else ""

    canonique = ""
    for lien in _LIEN.findall(html):
        attributs = {n.lower(): v for n, v in _ATTRIBUT.findall(lien)}
        if (attributs.get("rel") or "").lower() == "canonical" and attributs.get("href"):
            canonique = attributs["href"].strip()
            break

    date = normalize_date(_premier(metas, NOMS_DE_DATE))
    return {
        "document_title": titre or INCONNU,
        "publication_date": date["date"],
        "date_reason": date["reason"],
        "publisher": _premier(metas, NOMS_D_EDITEUR) or INCONNU,
        "language_declared": _langue_declaree(_premier(metas, NOMS_DE_LANGUE)),
        "canonical_url": canonique or INCONNU,
        "document_type": "text/html",
        "source": "html-meta",
        "available": True,
    }


def from_pdf(contenu: bytes) -> Dict[str, Any]:
    """
    Extrait les métadonnées d'un PDF, si une bibliothèque le permet.

    Sans `pypdf`, ce module **dit qu'il n'a pas pu lire** au lieu de rendre des
    champs vides qui ressembleraient à un PDF sans métadonnées. Les deux
    situations demandent des actions différentes, et les confondre ferait
    chercher au mauvais endroit.
    """
    try:
        import pypdf
    except ImportError:
        try:
            import PyPDF2 as pypdf  # noqa: N813 — ancien nom, même interface
        except ImportError:
            return {
                "available": False,
                "source": "pdf-metadata",
                "reason": (
                    "Ni `pypdf` ni `PyPDF2` n'est installé : les métadonnées du PDF "
                    "n'ont pas pu être lues. Ce n'est pas « un PDF sans métadonnées »."
                ),
                "document_title": INCONNU,
                "publication_date": INCONNU,
                "date_reason": "Bibliothèque PDF indisponible.",
                "publisher": INCONNU,
                "language_declared": INCONNU,
                "canonical_url": INCONNU,
                "document_type": "application/pdf",
            }

    import io

    try:
        lecteur = pypdf.PdfReader(io.BytesIO(contenu))
        info = lecteur.metadata or {}
    except Exception as erreur:  # noqa: BLE001 — un PDF cassé est une donnée externe
        return {
            "available": False,
            "source": "pdf-metadata",
            "reason": f"PDF illisible : {erreur}",
            "document_title": INCONNU,
            "publication_date": INCONNU,
            "date_reason": "PDF illisible.",
            "publisher": INCONNU,
            "language_declared": INCONNU,
            "canonical_url": INCONNU,
            "document_type": "application/pdf",
        }

    brute = str(info.get("/CreationDate") or "")
    # `D:20240315120000+00'00'` — la forme PDF, ramenée à une date ISO.
    lisible = re.sub(r"^D:(\d{4})(\d{2})(\d{2}).*$", r"\1-\2-\3", brute) if brute else ""
    date = normalize_date(lisible)

    return {
        "available": True,
        "source": "pdf-metadata",
        "document_title": str(info.get("/Title") or "").strip() or INCONNU,
        "publication_date": date["date"],
        "date_reason": date["reason"],
        "publisher": str(info.get("/Author") or "").strip() or INCONNU,
        "language_declared": INCONNU,
        "canonical_url": INCONNU,
        "document_type": "application/pdf",
    }


def extract(contenu: bytes, content_type: str = "", url: str = "") -> Dict[str, Any]:
    """
    Extrait les métadonnées d'un document, selon son type.

    Un type inconnu ne devine pas : il rend des champs `unknown` et le dit.
    """
    mime = (content_type or "").lower()
    if "pdf" in mime:
        return from_pdf(contenu)
    if "html" in mime or "xml" in mime:
        return from_html(contenu, url)
    return {
        "available": False,
        "source": "none",
        "reason": f"Aucun extracteur pour « {mime or 'type non déclaré'} ».",
        "document_title": INCONNU,
        "publication_date": INCONNU,
        "date_reason": "Type de document non pris en charge.",
        "publisher": INCONNU,
        "language_declared": INCONNU,
        "canonical_url": INCONNU,
        "document_type": mime or INCONNU,
    }


def apply_to(document: Any, metadonnees: Dict[str, Any]) -> Any:
    """
    Reporte les métadonnées sur un `AcquiredDocument`, sans écraser le registre.

    L'institution, le rang, le pays et le domaine viennent du registre et ne
    sont **jamais** touchés ici : un document qui se déclare officiel ne gagne
    rien à le dire.
    """
    for champ in ("document_title", "publication_date", "publisher",
                  "language_declared", "canonical_url", "document_type"):
        valeur = metadonnees.get(champ, INCONNU)
        if valeur and valeur != INCONNU:
            setattr(document, champ, valeur)

    document.provenance["metadata_source"] = metadonnees.get("source", "none")
    document.provenance["metadata_available"] = metadonnees.get("available", False)
    document.provenance["date_reason"] = metadonnees.get("date_reason", "")
    return document


def metadata_report() -> Dict[str, Any]:
    """Décrit ce que l'extraction lit, et ce qu'elle refuse de deviner."""
    return {
        "html_fields": sorted(set(NOMS_DE_TITRE + NOMS_DE_DATE + NOMS_D_EDITEUR)),
        "pdf_fields": ["/Title", "/Author", "/CreationDate"],
        "never_inferred": [
            "publication_date depuis retrieval_date, l'URL ou le nom du fichier",
            "institution, rang, pays : ils viennent du registre, jamais du document",
        ],
        "ambiguous_dates": "unknown, avec la raison",
        "not_detected": [
            "une date de publication absente des métadonnées mais présente dans le "
            "texte — la lire demanderait de comprendre le document",
            "un titre trompeur : le document est cru sur son titre, faute d'autre source",
            "les métadonnées d'un PDF sans bibliothèque PDF — l'indisponibilité est "
            "rapportée, pas confondue avec un PDF sans métadonnées",
        ],
    }
