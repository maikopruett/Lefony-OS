/* Included by selectable_table_view.cpp only for the Prime target. */
bool SelectableTableView::touchCellAt(int x, int y, int * column, int * row) {
  KDPoint origin = touchOrigin();
  if (!bounds().contains(KDPoint(x - origin.x(), y - origin.y()))) return false;
  KDPoint contentOrigin = m_contentView.touchOrigin();
  KDPoint point(x - contentOrigin.x(), y - contentOrigin.y());
  int lastRow = std::min(dataSource()->numberOfRows(), firstDisplayedRowIndex() + numberOfDisplayableRows());
  int lastColumn = std::min(dataSource()->numberOfColumns(), firstDisplayedColumnIndex() + numberOfDisplayableColumns());
  for (int j = firstDisplayedRowIndex(); j < lastRow; j++) {
    for (int i = firstDisplayedColumnIndex(); i < lastColumn; i++) {
      if (m_contentView.cellFrame(i, j).contains(point) &&
          (!m_delegate || m_delegate->canSelectCellByTouch(this, i, j))) {
        *column = i; *row = j;
        return true;
      }
    }
  }
  return false;
}

bool SelectableTableView::handleTouch(const Ion::Touch::Event & touch) {
  using Ion::Touch::Phase;
  int column = -1, row = -1;
  if (touch.phase == Phase::Down) {
    KDPoint origin = touchOrigin();
    if (!bounds().contains(KDPoint(touch.x - origin.x(), touch.y - origin.y()))) return false;
    m_touchColumn = m_touchRow = -1;
    touchCellAt(touch.x, touch.y, &m_touchColumn, &m_touchRow);
    m_touchOffset = contentOffset();
    m_touchTracking = true;
    if (m_touchRow >= 0) {
      unhighlightSelectedCell();
      if (auto cell = cellAtLocation(m_touchColumn, m_touchRow)) {
        if (!cell->isHighlighted()) cell->setHighlighted(true);
      }
    }
    return true; // Blank space can start a scroll, but never an activation.
  }
  if (!m_touchTracking) return false;
  if (touch.phase == Phase::Cancel || touch.dragging) {
    if (m_touchRow >= 0) {
      if (auto cell = cellAtLocation(m_touchColumn, m_touchRow)) cell->setHighlighted(false);
      m_touchColumn = m_touchRow = -1;
    }
    if (touch.phase == Phase::Cancel) if (auto cell = selectedCell()) {
      if (!cell->isHighlighted()) cell->setHighlighted(true);
    }
  }
  if (touch.phase == Phase::Cancel) { m_touchTracking = false; return true; }
  if (touch.dragging) {
    // Stop highlights/animation before visible cells are recycled for other
    // rows. Keeping an offscreen selection animated retains stale cell state.
    for (int j = firstDisplayedRowIndex(); j < firstDisplayedRowIndex() + numberOfDisplayableRows(); j++) {
      for (int i = firstDisplayedColumnIndex(); i < firstDisplayedColumnIndex() + numberOfDisplayableColumns(); i++) {
        if (auto cell = cellAtLocation(i, j)) {
          if (cell->isHighlighted()) cell->setHighlighted(false);
        }
      }
    }
    int maxX = std::max(0, int(contentSize().width() - maxContentWidthDisplayableWithoutScrolling()));
    int maxY = std::max(0, int(contentSize().height() - maxContentHeightDisplayableWithoutScrolling()));
    int x = std::max(0, std::min(maxX, m_touchOffset.x() + touch.startX - touch.x));
    int y = std::max(0, std::min(maxY, m_touchOffset.y() + touch.startY - touch.y));
    setContentOffset(KDPoint(x, y));
    // Transparent launcher cells need the whole viewport background cleared
    // when scrolling by pixels rather than jumping between selected rows.
    markRectAsDirty(bounds());
  }
  if (touch.phase != Phase::Up) return true;
  m_touchTracking = false;
  bool activate = !touch.dragging && touchCellAt(touch.x, touch.y, &column, &row)
    && column == m_touchColumn && row == m_touchRow;
  if (m_touchRow >= 0) {
    if (auto cell = cellAtLocation(m_touchColumn, m_touchRow)) cell->setHighlighted(false);
  }
  if (!activate) {
    if (auto cell = selectedCell()) {
      if (!cell->isHighlighted()) cell->setHighlighted(true);
    }
    return true;
  }
  selectCellAtLocation(column, row);
  // Delegates may redirect selection away from disabled/placeholder rows.
  if (selectedColumn() != column || selectedRow() != row) return true;
  // A touch can revisit an already selected cell while a tab or toolbar owns
  // keyboard focus. Selection only changes focus when its coordinates change.
  if (auto cell = selectedCell()) {
    Container::activeApp()->setFirstResponder(cell->responder() ? cell->responder() : this);
  }
  // Use normal controller validation, exam-mode checks and editable-cell
  // responders. App clears its touch capture before this can change screens.
  Container::activeApp()->processEvent(Ion::Events::OK);
  return true;
}
