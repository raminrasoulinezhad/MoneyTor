# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Noncommercial use permitted. Commercial use requires a separate license;
# contact the author. Provided "as is", without warranty of any kind.

"""Build a Qt stylesheet (QSS) from :class:`ThemeTokens`.

Widgets opt into styling via objectName/property selectors (e.g.
``#KpiCard``, ``#MetricValue``) so the same QSS drives both themes — switching
themes is just re-applying ``build_qss`` with the other token set.
"""

from __future__ import annotations

from .tokens import ThemeTokens


def build_qss(t: ThemeTokens) -> str:
    """Return a full application stylesheet for the given tokens."""
    return f"""
    * {{
        font-family: {t.font_family};
        font-size: {t.font_size_base}px;
        color: {t.text};
    }}
    QMainWindow, #Root {{ background: {t.bg}; }}

    /* Sidebar */
    #Sidebar {{
        background: {t.surface};
        border-right: 1px solid {t.border};
    }}
    #SidebarTitle {{
        font-size: {t.font_size_label}px;
        color: {t.text_muted};
        text-transform: uppercase;
        letter-spacing: 1px;
    }}
    QCheckBox, QTreeWidget {{ background: transparent; border: none; }}
    QTreeWidget::item {{ padding: 4px 2px; }}
    QTreeWidget::item:hover {{ background: {t.surface_alt}; border-radius: {t.radius_sm}px; }}

    /* Cards */
    #KpiCard, #Panel {{
        background: {t.surface};
        border: 1px solid {t.border};
        border-radius: {t.radius}px;
    }}
    #KpiTitle, #PanelTitle {{
        font-size: {t.font_size_label}px;
        color: {t.text_muted};
        text-transform: uppercase;
        letter-spacing: 1px;
    }}
    #MetricValue {{
        font-size: {t.font_size_metric}px;
        font-weight: 700;
        color: {t.text};
    }}
    #MetricPositive {{ font-size: {t.font_size_metric}px; font-weight: 700; color: {t.positive}; }}
    #MetricNegative {{ font-size: {t.font_size_metric}px; font-weight: 700; color: {t.negative}; }}
    #CardSubtitle {{ font-size: {t.font_size_label}px; color: {t.text_muted}; }}
    #Placeholder {{ color: {t.text_muted}; }}

    /* Inputs (search box, chart selector, dialog fields) */
    QLineEdit, QComboBox, QAbstractSpinBox {{
        background: {t.surface_alt};
        color: {t.text};
        border: 1px solid {t.border};
        border-radius: {t.radius_sm}px;
        padding: 6px 10px;
        selection-background-color: {t.accent};
        selection-color: white;
    }}
    QLineEdit:focus, QComboBox:focus {{ border: 1px solid {t.accent}; }}
    QLineEdit {{ color: {t.text}; }}
    QComboBox QAbstractItemView {{
        background: {t.surface};
        color: {t.text};
        selection-background-color: {t.accent};
        selection-color: white;
    }}

    /* Dialogs (e.g. the 2FA prompt) inherit the app palette */
    QDialog, QMessageBox, QInputDialog {{ background: {t.surface}; }}
    QDialog QLabel, QMessageBox QLabel, QInputDialog QLabel {{ color: {t.text}; }}

    /* Buttons */
    QPushButton {{
        background: {t.accent};
        color: white;
        border: none;
        border-radius: {t.radius_sm}px;
        padding: 8px 16px;
        font-weight: 600;
    }}
    QPushButton:hover {{ background: {t.accent_hover}; }}
    QToolBar {{
        background: {t.surface};
        border-bottom: 1px solid {t.border};
        spacing: {t.spacing}px;
    }}

    /* Error banner */
    #ErrorBanner {{
        background: {t.negative};
        border-bottom: 1px solid {t.border};
    }}
    #ErrorBannerText {{ color: white; font-weight: 600; }}
    #ErrorBannerDismiss {{ background: rgba(0, 0, 0, 0.25); }}

    /* Fetch progress bar (shown only while refreshing) */
    #FetchProgress {{
        background: {t.surface_alt};
        border: none;
        border-bottom: 1px solid {t.border};
        color: {t.text};
        font-size: {t.font_size_label}px;
        font-weight: 600;
        text-align: center;
    }}
    #FetchProgress::chunk {{ background: {t.accent}; }}

    /* Holdings table */
    QTableWidget {{
        background: {t.surface};
        alternate-background-color: {t.surface_alt};
        gridline-color: {t.border};
        border: 1px solid {t.border};
        border-radius: {t.radius}px;
        selection-background-color: {t.accent};
        selection-color: white;
    }}
    QHeaderView::section {{
        background: {t.surface};
        color: {t.text_muted};
        border: none;
        border-bottom: 1px solid {t.border};
        padding: 8px;
        font-size: {t.font_size_label}px;
        text-transform: uppercase;
    }}
    QTableWidget::item {{ padding: 6px 8px; }}
    /* The rank-gutter corner (top-left): match the column headers, label "#". */
    QTableView QTableCornerButton::section {{
        background: {t.surface};
        border: none;
        border-bottom: 1px solid {t.border};
    }}
    #RankCorner {{
        background: transparent;
        color: {t.text_muted};
        font-size: {t.font_size_label}px;
    }}
    """
