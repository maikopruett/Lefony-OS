/* Included by button.cpp. */
bool Button::handleTouch(const Ion::Touch::Event & touch) {
  using Ion::Touch::Phase;
  if (touch.phase == Phase::Down) {
    m_touchTracking = touchContains(touch.x, touch.y);
    if (!m_touchTracking) return false;
    m_touchWasHighlighted = isHighlighted();
    setHighlighted(true);
    return true;
  }
  if (!m_touchTracking) return false;
  bool inside = touchContains(touch.x, touch.y);
  setHighlighted(m_touchWasHighlighted || (!touch.dragging && inside && touch.phase != Phase::Cancel));
  if (touch.phase != Phase::Up && touch.phase != Phase::Cancel) return true;
  m_touchTracking = false;
  setHighlighted(m_touchWasHighlighted);
  if (touch.phase == Phase::Up && !touch.dragging && inside) {
    // Invoke this visible button, independently of the keyboard selection.
    handleEvent(Ion::Events::OK);
  }
  return true;
}
