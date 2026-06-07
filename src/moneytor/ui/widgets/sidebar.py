"""Collapsible left sidebar: family checklist + account tree.

Emits :attr:`Sidebar.selectionChanged` with the set of currently-checked
account ids whenever the user toggles a person or account. An empty selection
means "show everything" (handled by the window).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from moneytor.ui.viewmodels import SidebarModel

_ACCOUNT_ID_ROLE = Qt.ItemDataRole.UserRole


class Sidebar(QWidget):
    """Family/account selector panel."""

    selectionChanged = Signal(frozenset)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(260)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Accounts")
        title.setObjectName("SidebarTitle")

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.itemChanged.connect(self._on_item_changed)

        layout.addWidget(title)
        layout.addWidget(self._tree, stretch=1)

    def set_model(self, model: SidebarModel) -> None:
        """Rebuild the tree from ``model`` (all items checked by default)."""
        self._tree.blockSignals(True)
        self._tree.clear()
        for person in model.people:
            person_item = QTreeWidgetItem([person.name])
            person_item.setFlags(person_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            person_item.setCheckState(0, Qt.CheckState.Checked)
            for account in person.accounts:
                account_item = QTreeWidgetItem([account.label])
                account_item.setFlags(account_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                account_item.setCheckState(0, Qt.CheckState.Checked)
                account_item.setData(0, _ACCOUNT_ID_ROLE, account.id)
                person_item.addChild(account_item)
            self._tree.addTopLevelItem(person_item)
        self._tree.expandAll()
        self._tree.blockSignals(False)

    def selected_account_ids(self) -> frozenset[str]:
        """Account ids currently checked in the tree."""
        selected: set[str] = set()
        for i in range(self._tree.topLevelItemCount()):
            person_item = self._tree.topLevelItem(i)
            if person_item is None:
                continue
            for j in range(person_item.childCount()):
                child = person_item.child(j)
                if child is None or child.checkState(0) != Qt.CheckState.Checked:
                    continue
                account_id = child.data(0, _ACCOUNT_ID_ROLE)
                if isinstance(account_id, str):
                    selected.add(account_id)
        return frozenset(selected)

    def _on_item_changed(self, item: QTreeWidgetItem, _column: int) -> None:
        # Toggling a person cascades to its accounts.
        if item.childCount() > 0:
            self._tree.blockSignals(True)
            for j in range(item.childCount()):
                child = item.child(j)
                if child is not None:
                    child.setCheckState(0, item.checkState(0))
            self._tree.blockSignals(False)
        self.selectionChanged.emit(self.selected_account_ids())
