const form = document.getElementById('calculator-form');
const resultEmpty = document.getElementById('resultEmpty');
const resultContent = document.getElementById('resultContent');
const deadlineText = document.getElementById('deadlineText');
const metaText = document.getElementById('metaText');
const reminderList = document.getElementById('reminderList');
const leadDialog = document.getElementById('leadDialog');

const holidayProfiles = {
  federal: ['01-01', '07-04', '11-11', '12-25'],
  california: ['01-01', '03-31', '07-04', '11-28', '12-25'],
  newyork: ['01-01', '02-12', '07-04', '11-28', '12-25']
};

let latestResult = null;
let exportUnlocked = false;

function isWeekend(date) {
  const day = date.getDay();
  return day === 0 || day === 6;
}

function isHoliday(date, profile) {
  const monthDay = `${String(date.getMonth() + 1).padStart(2, '0')}-${String(
    date.getDate()
  ).padStart(2, '0')}`;
  return holidayProfiles[profile].includes(monthDay);
}

function isBusinessDay(date, profile) {
  return !isWeekend(date) && !isHoliday(date, profile);
}

function moveByOne(date, direction) {
  const next = new Date(date);
  next.setDate(next.getDate() + (direction === 'after' ? 1 : -1));
  return next;
}

function calculateDeadline({ triggerDate, direction, dayCount, countMethod, rollRule, jurisdiction }) {
  let current = new Date(`${triggerDate}T00:00:00`);

  if (countMethod === 'calendar') {
    current.setDate(current.getDate() + (direction === 'after' ? dayCount : -dayCount));
  } else {
    let traversed = 0;
    while (traversed < dayCount) {
      current = moveByOne(current, direction);
      if (countMethod === 'business' && !isWeekend(current)) traversed += 1;
      if (countMethod === 'court' && isBusinessDay(current, jurisdiction)) traversed += 1;
    }
  }

  if (rollRule !== 'none') {
    while (!isBusinessDay(current, jurisdiction)) {
      current = moveByOne(current, rollRule === 'next' ? 'after' : 'before');
    }
  }

  return current;
}

function formatDate(date) {
  return new Intl.DateTimeFormat('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  }).format(date);
}

function toIcsDate(date) {
  const y = date.getUTCFullYear();
  const m = String(date.getUTCMonth() + 1).padStart(2, '0');
  const d = String(date.getUTCDate()).padStart(2, '0');
  return `${y}${m}${d}`;
}

function downloadICS() {
  if (!latestResult) return;

  const deadlineDate = toIcsDate(latestResult.deadline);
  const reminders = latestResult.reminders
    .map((entry, idx) => {
      const date = toIcsDate(entry.date);
      return `BEGIN:VEVENT\nUID:reminder-${idx}@clio\nDTSTAMP:${deadlineDate}T120000Z\nDTSTART;VALUE=DATE:${date}\nSUMMARY:Reminder: legal deadline in ${entry.offset} day(s)\nEND:VEVENT`;
    })
    .join('\n');

  const content = `BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Clio//Deadline Calculator//EN\nBEGIN:VEVENT\nUID:deadline-main@clio\nDTSTAMP:${deadlineDate}T120000Z\nDTSTART;VALUE=DATE:${deadlineDate}\nSUMMARY:Legal deadline\nEND:VEVENT\n${reminders}\nEND:VCALENDAR`;

  const blob = new Blob([content], { type: 'text/calendar;charset=utf-8' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = 'legal-deadline.ics';
  link.click();
  URL.revokeObjectURL(link.href);
}

form.addEventListener('submit', (event) => {
  event.preventDefault();

  const data = {
    triggerDate: document.getElementById('triggerDate').value,
    direction: document.getElementById('direction').value,
    dayCount: Number(document.getElementById('dayCount').value),
    countMethod: document.getElementById('countMethod').value,
    rollRule: document.getElementById('rollRule').value,
    jurisdiction: document.getElementById('jurisdiction').value
  };

  const selectedOffsets = [...document.querySelectorAll('.chips input:checked')]
    .map((checkbox) => Number(checkbox.value))
    .sort((a, b) => b - a);

  const deadline = calculateDeadline(data);
  const reminders = selectedOffsets
    .map((offset) => ({
      offset,
      date: new Date(deadline.getFullYear(), deadline.getMonth(), deadline.getDate() - offset)
    }))
    .filter(({ date }) => !Number.isNaN(date.getTime()));

  latestResult = { data, deadline, reminders };

  deadlineText.textContent = formatDate(deadline);
  metaText.textContent = `${data.dayCount} ${data.countMethod} day(s), ${data.direction} ${data.triggerDate}, ${
    data.rollRule === 'none' ? 'no roll adjustment' : `${data.rollRule} roll adjustment`
  }, ${data.jurisdiction} profile.`;

  reminderList.innerHTML = reminders.length
    ? reminders.map((entry) => `<li>${entry.offset} day reminder — ${formatDate(entry.date)}</li>`).join('')
    : '<li>No reminders selected.</li>';

  resultEmpty.hidden = true;
  resultContent.hidden = false;
});

document.getElementById('resetBtn').addEventListener('click', () => {
  form.reset();
  resultContent.hidden = true;
  resultEmpty.hidden = false;
  latestResult = null;
});

document.getElementById('downloadIcs').addEventListener('click', () => {
  if (!exportUnlocked) {
    leadDialog.showModal();
    return;
  }
  downloadICS();
});

document.getElementById('connectCalendar').addEventListener('click', () => {
  if (!exportUnlocked) {
    leadDialog.showModal();
    return;
  }
  window.alert('Thanks! In production, this would connect to Clio calendar integrations.');
});

document.getElementById('closeDialog').addEventListener('click', () => leadDialog.close());

document.getElementById('leadForm').addEventListener('submit', (event) => {
  event.preventDefault();
  const email = document.getElementById('leadEmail').value;
  const firm = document.getElementById('leadFirm').value;
  if (!email || !firm) return;

  exportUnlocked = true;
  leadDialog.close();
  downloadICS();
});
