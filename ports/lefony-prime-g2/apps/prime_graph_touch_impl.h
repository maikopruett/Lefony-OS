/* Included in Shared namespace by zoom_curve_view_controller.cpp. */
void ZoomCurveViewController::focusForTouch() {
  Container::activeApp()->setFirstResponder(this);
}

bool ZoomCurveViewController::handleTouch(const Ion::Touch::Event & touch) {
  using Ion::Touch::Phase;
  CurveView * graph = curveView();
  if (touch.phase == Phase::Down) {
    m_touchTracking = graph->touchContains(touch.x, touch.y);
    if (!m_touchTracking) return false;
    focusForTouch();
    m_touchOnOK = graph->touchOnOK(touch.x, touch.y);
    m_touchOnBanner = graph->touchOnBanner(touch.x, touch.y);
    if (touch.contacts == 2 && (!graph->touchContains(touch.x2, touch.y2) ||
        graph->touchOnBanner(touch.x2, touch.y2) || graph->touchOnOK(touch.x2, touch.y2))) {
      m_touchTracking = false;
      return true;
    }
  }
  if (!m_touchTracking) return false;
  if (touch.contactsChanged && touch.contacts == 2 &&
      (!graph->touchContains(touch.x2, touch.y2) || graph->touchOnBanner(touch.x2, touch.y2) ||
       graph->touchOnOK(touch.x2, touch.y2) || !graph->touchContains(touch.x, touch.y) ||
       graph->touchOnBanner(touch.x, touch.y) || graph->touchOnOK(touch.x, touch.y))) {
    m_touchTracking = false;
    m_touchGesture = PrimeG2::GraphGesture();
    return true;
  }
  if (touch.phase == Phase::Cancel || touch.phase == Phase::Up) {
    m_touchTracking = false;
    m_touchGesture = PrimeG2::GraphGesture();
    if (touch.phase == Phase::Up && !touch.dragging && touch.contacts == 1 &&
        ((m_touchOnOK && graph->touchOnOK(touch.x, touch.y)) ||
         (m_touchOnBanner && graph->touchOnBanner(touch.x, touch.y)))) {
      // The same curve options as the physical OK key.
      Container::activeApp()->setFirstResponder(this);
      handleEvent(Ion::Events::OK);
    }
    return true;
  }
  if (m_touchOnOK || m_touchOnBanner) return true;
  PrimeG2::GraphGesture::Delta delta;
  if (m_touchGesture.update(touch, &delta)) {
    auto range = interactiveCurveViewRange();
    KDPoint origin = graph->touchOrigin();
    float anchorX = range->xMin() + (delta.fromX - origin.x()) * graph->pixelWidth();
    float anchorY = range->yMax() - (delta.fromY - origin.y()) * graph->pixelHeight();
    // Zoom about the old centroid, then keep that graph point under the new
    // centroid. Use the actual post-zoom scale, including range limit clamps.
    if (delta.ratio != 1.f) range->zoom(delta.ratio, anchorX, anchorY);
    range->panWithVector((delta.fromX - delta.toX) * graph->pixelWidth(),
                         (delta.toY - delta.fromY) * graph->pixelHeight());
    graph->reload();
  }
  return true;
}
