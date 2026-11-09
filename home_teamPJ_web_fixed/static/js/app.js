document.addEventListener("DOMContentLoaded", () => {
  const repeat = document.getElementById("repeat-type");
  if (repeat) {
    const dateField = document.getElementById("date-field");
    const weekdayField = document.getElementById("weekday-field");
    const update = () => {
      const weekly = repeat.value === "毎週";
      dateField.hidden = weekly;
      weekdayField.hidden = !weekly;
    };
    repeat.addEventListener("change", update);
    update();
  }
});
