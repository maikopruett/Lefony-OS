// SPDX-License-Identifier: CC-BY-NC-SA-4.0
// Included in Home's controller.cpp; all gestures use normal touch dispatch.
void Controller::ContentView::showDraggedIcon(const Image *image,int x,int y) {
  m_dragImage.setImage(image);
  if(image) {
    KDPoint origin=touchOrigin();
    int left=std::max(0,std::min(int(bounds().width())-55,x-origin.x()-27));
    int top=std::max(0,std::min(int(bounds().height())-56,y-origin.y()-28));
    m_dragImage.setFrame(KDRect(left,top,55,56),false);
  } else m_dragImage.setFrame(KDRect(0,0,0,0),false);
  markRectAsDirty(bounds());
}

int Controller::homeTouchIndex(int x,int y,bool clamp) {
  auto table=m_view.selectableTableView();KDPoint origin=table->touchOrigin();
  x-=origin.x();y-=origin.y();
  if(clamp) {
    x=std::max(int(k_sideMargin),std::min(int(table->bounds().width())-k_sideMargin-1,x));
    y=std::max(0,std::min(int(table->bounds().height())-1,y));
  } else if(x<k_sideMargin || x>=table->bounds().width()-k_sideMargin || y<0 || y>=table->bounds().height()) return -1;
  int column=(x-k_sideMargin+table->contentOffset().x())/k_cellWidth;
  int row=(y+table->contentOffset().y())/k_cellHeight;
  int index=row*k_numberOfColumns+column;
  return index<numberOfIcons()?index:(clamp?numberOfIcons()-1:-1);
}

void Controller::reloadHomeDrag() {
  auto table=m_view.selectableTableView();
  table->deselectTable();table->reloadData(false);
  int selected=m_homeDragPosition;
  if(selected>=0 && selected<numberOfIcons()) table->selectCellAtLocation(selected%k_numberOfColumns,selected/k_numberOfColumns);
  m_view.invalidateDrag();
}

void Controller::cancelHomeDrag() {
  m_homeTouchTracking=false;
  if(!m_homeDragging) return;
  m_homeDragging=false;NativeApps::reloadMenuOrder();
  m_view.showDraggedIcon(nullptr,0,0);reloadHomeDrag();
}

bool Controller::handleHomeTouch(const Ion::Touch::Event &touch) {
  using Ion::Touch::Phase;
  if(touch.phase==Phase::Cancel || touch.contacts>1) {cancelHomeDrag();return false;}
  if(touch.phase==Phase::Down) {
    cancelHomeDrag();m_homeDragPosition=homeTouchIndex(touch.x,touch.y,false);
    m_homeDragStart=m_homeDragPosition;m_homeTouchTracking=m_homeDragPosition>=0;
    m_homeTouchTime=Ion::Timing::millis();m_homeTouchX=touch.x;m_homeTouchY=touch.y;
    return false; // Ordinary taps and swipes keep the table's existing behavior.
  }
  if(!m_homeTouchTracking) return false;
  m_homeTouchX=touch.x;m_homeTouchY=touch.y;
  if(!m_homeDragging) {
    if(touch.dragging || touch.phase==Phase::Up) m_homeTouchTracking=false;
    return false;
  }
  if(touch.phase==Phase::Up) {
    if(homeTouchIndex(touch.x,touch.y,true)<0) {cancelHomeDrag();return true;}
    m_homeTouchTracking=false;m_homeDragging=false;m_view.showDraggedIcon(nullptr,0,0);
    bool saved=m_homeDragStart==m_homeDragPosition || NativeApps::saveMenuOrder();
    if(!saved) NativeApps::reloadMenuOrder();
    reloadHomeDrag();
    if(!saved) App::app()->displayWarning(I18n::Message::StorageMemoryFull1);
    return true; // Dropping never activates the app underneath the finger.
  }
  updateHomeDrag(false);return true;
}

void Controller::updateHomeDrag(bool scroll) {
  auto table=m_view.selectableTableView();
  uint64_t now=Ion::Timing::millis();KDPoint origin=table->touchOrigin();
  if(scroll && now-m_homeScrollTime>=600) {
    int y=m_homeTouchY-origin.y(),direction=y<32?-1:(y>table->bounds().height()-32?1:0);
    if(direction) {
      int maxY=std::max(0,numberOfRows()*k_cellHeight+k_bottomMargin-int(table->bounds().height()));
      int offset=std::max(0,std::min(maxY,int(table->contentOffset().y())+direction*k_cellHeight));
      table->setContentOffset(KDPoint(0,offset));m_homeScrollTime=now;
    }
  }
  int target=homeTouchIndex(m_homeTouchX,m_homeTouchY,true);
  if(target>=0 && target!=m_homeDragPosition) {
    NativeApps::moveMenuIcon(m_homeDragPosition,target);m_homeDragPosition=target;reloadHomeDrag();
  }
  m_view.showDraggedIcon(m_homeDragIcon,m_homeTouchX,m_homeTouchY);
}

bool Controller::refreshHomeDrag() {
  if(!m_homeTouchTracking) return false;
  if(NativeApps::catalogRevision()!=m_catalogRevision) {cancelHomeDrag();return true;}
  uint64_t now=Ion::Timing::millis();
  if(!m_homeDragging && now-m_homeTouchTime>=600) {
    auto table=m_view.selectableTableView();
    table->SelectableTableView::handleTouch(Ion::Touch::Event()); // Cancel pending tap/scroll.
    m_homeDragging=true;m_homeDragIcon=NativeApps::menuIcon(m_homeDragPosition);
    m_homeScrollTime=now;reloadHomeDrag();
  }
  if(m_homeDragging) {updateHomeDrag(true);return true;}
  return false;
}
