# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

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
    QTreeWidget::item {{ padding: 2px 2px; }}
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

    /* Settings dialog */
    #SettingsNote {{ font-size: {t.font_size_label}px; color: {t.text_muted}; }}
    #SettingsError {{ color: {t.negative}; font-weight: 600; }}
    /* An explicit box: the default indicator is near-invisible on the dark
       surface, and these two checkboxes are the whole point of the panel. */
    #SettingsDialog QCheckBox {{ spacing: 10px; font-weight: 600; }}
    #SettingsDialog QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border: 1px solid {t.border};
        /* Not radius_sm: 8px on an 18px box rounds into a radio-button circle. */
        border-radius: 4px;
        background: {t.surface_alt};
    }}
    #SettingsDialog QCheckBox::indicator:hover {{ border: 1px solid {t.accent}; }}
    #SettingsDialog QCheckBox::indicator:checked {{
        background: {t.accent};
        border: 1px solid {t.accent};
    }}
    #SettingsDialog QCheckBox:disabled {{ color: {t.text_muted}; }}
    #SettingsDialog QCheckBox::indicator:disabled {{ background: {t.surface}; }}

    /* Inputs (search box, chart selector, dialog fields) */
    QLineEdit, QComboBox, QAbstractSpinBox {{
        background: {t.surface_alt};
        color: {t.text};
        border: 1px solid {t.border};
        border-radius: {t.radius_sm}px;
        padding: 4px 10px;
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
        padding: 6px 14px;
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
        padding: 4px 8px;
        font-size: {t.font_size_label}px;
        text-transform: uppercase;
    }}
    QTableWidget::item {{ padding: 2px 8px; }}
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
