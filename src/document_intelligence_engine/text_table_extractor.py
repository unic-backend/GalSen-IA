"""
Extracteur de tableaux pour le moteur d'intelligence documentaire GalSen IA.
"""

from typing import Any, Dict, List, Optional

from .interfaces import DocumentTableExtractor
from .types import DocumentItem


class TableExtractorImpl(DocumentTableExtractor):
    """
    Extracteur de tableaux présents sous forme textuelle dans un document.

    Il reconnaît les trois façons courantes de représenter un tableau en texte :
    colonnes séparées par des tabulations, tableaux Markdown en barres verticales,
    et lignes de type CSV. Les lignes consécutives partageant le même séparateur
    forment un tableau.
    """

    # Séparateur -> nombre minimum d'occurrences pour qu'une ligne soit une ligne de tableau
    _SEPARATORS = (('\t', 2), ('|', 2), (',', 3))

    # Un tableau doit avoir au moins un en-tête et une ligne de données
    _MIN_TABLE_ROWS = 2

    def extract_tables(self, document: DocumentItem) -> List[Dict[str, Any]]:
        """
        Extrait les tableaux d'un document.

        Args:
            document: Document à analyser

        Returns:
            Liste de tableaux, chacun décrit par son séparateur, ses en-têtes,
            ses lignes de données et son contenu brut
        """
        tables: List[Dict[str, Any]] = []
        current_rows: List[str] = []
        current_separator: Optional[str] = None

        for line in document.content.splitlines():
            separator = self._detect_separator(line)

            if separator is not None and separator == current_separator:
                # Le tableau en cours continue
                current_rows.append(line)
                continue

            # Changement de séparateur ou ligne hors tableau : on clôt le tableau courant
            self._flush(tables, current_rows, current_separator)

            if separator is not None:
                current_rows = [line]
                current_separator = separator
            else:
                current_rows = []
                current_separator = None

        self._flush(tables, current_rows, current_separator)
        return tables

    def _detect_separator(self, line: str) -> Optional[str]:
        """Retourne le séparateur de colonnes de la ligne, ou None si ce n'en est pas une."""
        for separator, minimum_count in self._SEPARATORS:
            if line.count(separator) >= minimum_count:
                return separator
        return None

    def _flush(self, tables: List[Dict[str, Any]], rows: List[str], separator: Optional[str]) -> None:
        """Ajoute le tableau en cours à la liste s'il est assez consistant."""
        if separator is None or len(rows) < self._MIN_TABLE_ROWS:
            return

        parsed = [self._split_row(row, separator) for row in rows]
        headers = parsed[0]
        data_rows = parsed[1:]

        tables.append({
            "type": "text_table",
            "separator": separator,
            "headers": headers,
            "rows": data_rows,
            "row_count": len(data_rows),
            "column_count": len(headers),
            "content": '\n'.join(rows),
        })

    def _split_row(self, row: str, separator: str) -> List[str]:
        """Découpe une ligne en cellules et nettoie les espaces superflus."""
        cells = [cell.strip() for cell in row.split(separator)]

        # Un tableau Markdown commence et finit par une barre : cela produit des
        # cellules vides aux extrémités qu'il faut retirer
        if separator == '|':
            if cells and not cells[0]:
                cells = cells[1:]
            if cells and not cells[-1]:
                cells = cells[:-1]

        return cells
