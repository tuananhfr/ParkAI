"""
Flow Layout - Auto-wrap widgets like CSS flexbox
Source: Qt Documentation Examples
"""
from PyQt6.QtWidgets import QLayout
from PyQt6.QtCore import Qt, QRect, QSize, QPoint


class FlowLayout(QLayout):
    """Layout tự động wrap widgets khi hết chỗ"""

    def __init__(self, parent=None, margin=0, spacing=-1):
        super().__init__(parent)
        self.item_list = []
        self.m_hSpace = spacing
        self.m_vSpace = spacing
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item):
        self.item_list.append(item)

    def horizontalSpacing(self):
        if self.m_hSpace >= 0:
            return self.m_hSpace
        else:
            return self.smartSpacing(Qt.Orientation.Horizontal)

    def verticalSpacing(self):
        if self.m_vSpace >= 0:
            return self.m_vSpace
        else:
            return self.smartSpacing(Qt.Orientation.Vertical)

    def count(self):
        return len(self.item_list)

    def itemAt(self, index):
        if 0 <= index < len(self.item_list):
            return self.item_list[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self.item_list):
            return self.item_list.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        height = self.doLayout(QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self.item_list:
            size = size.expandedTo(item.minimumSize())
        margin = self.contentsMargins().left()
        size += QSize(2 * margin, 2 * margin)
        return size

    def doLayout(self, rect, testOnly):
        x = rect.x()
        y = rect.y()
        lineHeight = 0

        for item in self.item_list:
            spaceX = self.horizontalSpacing()
            spaceY = self.verticalSpacing()
            nextX = x + item.sizeHint().width() + spaceX

            if nextX - spaceX > rect.right() and lineHeight > 0:
                x = rect.x()
                y = y + lineHeight + spaceY
                nextX = x + item.sizeHint().width() + spaceX
                lineHeight = 0

            if not testOnly:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = nextX
            lineHeight = max(lineHeight, item.sizeHint().height())

        return y + lineHeight - rect.y()

    def smartSpacing(self, orientation):
        parent = self.parent()
        if not parent:
            return -1
        elif parent.isWidgetType():
            if orientation == Qt.Orientation.Horizontal:
                return parent.style().pixelMetric(
                    parent.style().PixelMetric.PM_LayoutHorizontalSpacing, None, parent
                )
            else:
                return parent.style().pixelMetric(
                    parent.style().PixelMetric.PM_LayoutVerticalSpacing, None, parent
                )
        else:
            return parent.spacing()
