// static/js/common/date.js
// 날짜 관련 유틸 (추가만; 전역 window.dateUtils 노출)

(function () {
  if (window.dateUtils) return; // 중복 방지

  // 오늘 날짜 YYYY-MM-DD
  function todayISO() {
    return new Date().toISOString().slice(0, 10);
  }

  // JS Date -> YYYY-MM-DD
  function toISODate(d) {
    if (!(d instanceof Date)) d = new Date(d);
    return d.toISOString().slice(0, 10);
  }

  // YYYY-MM-DD -> JS Date
  function fromISODate(s) {
    const [y, m, d] = s.split("-").map(Number);
    return new Date(y, m - 1, d);
  }

  // 주간(월~일) 범위: 기준일로부터 같은 주 월요일~일요일 반환
  function weekRange(date) {
    const d = (date instanceof Date) ? new Date(date) : fromISODate(date);
    const day = d.getDay(); // 0=일 ~ 6=토
    const diffToMonday = (day === 0 ? -6 : 1) - day; // 월요일까지 차이
    const monday = new Date(d);
    monday.setDate(d.getDate() + diffToMonday);
    const sunday = new Date(monday);
    sunday.setDate(monday.getDate() + 6);
    return [toISODate(monday), toISODate(sunday)];
  }

  // ±n일 이동
  function shiftDate(iso, n) {
    const d = fromISODate(iso);
    d.setDate(d.getDate() + n);
    return toISODate(d);
  }

  // 오늘을 기준으로 ±n주 이동 범위
  function shiftWeek(n) {
    const today = new Date();
    today.setDate(today.getDate() + n * 7);
    return weekRange(today);
  }

  // 외부 노출
  window.dateUtils = {
    todayISO,
    toISODate,
    fromISODate,
    weekRange,
    shiftDate,
    shiftWeek
  };
})();
