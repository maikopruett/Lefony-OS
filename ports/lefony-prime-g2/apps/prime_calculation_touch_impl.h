/* Included inside namespace Calculation by selectable_table_view.cpp. */
int CalculationSelectableTableView::historyTouchTarget(int x, int y, int * row) {
  KDPoint origin = touchOrigin();
  if (!bounds().contains(KDPoint(x - origin.x(), y - origin.y()))) return 0;
  int end = std::min(dataSource()->numberOfRows(), firstDisplayedRowIndex() + numberOfDisplayableRows());
  for (int j = firstDisplayedRowIndex(); j < end; j++) {
    auto cell = static_cast<HistoryViewCell *>(cellAtLocation(0, j));
    if (!cell) continue;
    auto contains = [x, y](View * view) {
      KDPoint p = view->touchOrigin();
      return view->bounds().contains(KDPoint(x - p.x(), y - p.y()));
    };
    if (!contains(cell)) continue;
    *row = j;
    if (contains(cell->inputView())) return 1;
    if (contains(cell->outputView()))
      return cell->outputView()->touchTargetsApproximate(x) ? 3 : 2;
    return 0; // Separators and empty space do not recall anything.
  }
  return 0;
}

bool CalculationSelectableTableView::handleTouch(const Ion::Touch::Event & touch) {
  using Ion::Touch::Phase;
  if (touch.phase == Phase::Down) {
    KDPoint origin = touchOrigin();
    if (!bounds().contains(KDPoint(touch.x - origin.x(), touch.y - origin.y()))) return false;
    m_historyTouchRow = -1;
    m_historyTouchTarget = historyTouchTarget(touch.x, touch.y, &m_historyTouchRow);
    m_historyTouchOffset = contentOffset();
    m_historyTouchTracking = true;
    return true;
  }
  if (!m_historyTouchTracking) return false;
  if (touch.phase == Phase::Cancel) {
    m_historyTouchTracking = false;
    return true;
  }
  if (touch.dragging) {
    m_historyTouchTarget = 0; // A drag can never turn back into a tap.
    unhighlightSelectedCell();
    int maxY = std::max(0, int(contentSize().height() - maxContentHeightDisplayableWithoutScrolling()));
    int y = std::max(0, std::min(maxY, m_historyTouchOffset.y() + touch.startY - touch.y));
    setContentOffset(KDPoint(m_historyTouchOffset.x(), y));
    markRectAsDirty(bounds());
  }
  if (touch.phase != Phase::Up) return true;
  m_historyTouchTracking = false;
  int row = -1;
  int target = historyTouchTarget(touch.x, touch.y, &row);
  if (!touch.dragging && target && target == m_historyTouchTarget && row == m_historyTouchRow) {
    // Read the visible row before keyboard selection can expand/recycle it.
    static_cast<HistoryController *>(parentResponder())->recallByTouch(row, target == 1, target == 3);
  }
  return true;
}
