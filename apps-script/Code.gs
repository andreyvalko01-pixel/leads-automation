/**
 * Приймає заявки від сервісу (POST JSON) і дописує рядок у таблицю.
 *
 * Встановлення:
 *  1. Розширення → Apps Script, вставити цей код.
 *  2. Розгорнути → Нове розгортання → Веб-застосунок,
 *     "Виконувати як": я, "Доступ": усі.
 *  3. URL розгортання вставити в SHEETS_WEBHOOK_URL сервісу.
 */

const SHEET_NAME = 'Заявки';
const HEADERS = ['ID', 'Дата', "Ім'я", 'Телефон', 'Email', 'Повідомлення', 'Форма', 'Сторінка',
                 'utm_source', 'utm_medium', 'utm_campaign', 'Дубль', 'Статус'];

function getSheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
    sheet.appendRow(HEADERS);
    sheet.getRange(1, 1, 1, HEADERS.length).setFontWeight('bold').setBackground('#f1f3f4');
    sheet.setFrozenRows(1);
  }
  return sheet;
}

function doPost(e) {
  // одночасні заявки не повинні перезаписати одна одну
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);

  try {
    const lead = JSON.parse(e.postData.contents);
    const sheet = getSheet_();

    // якщо сервіс повторив запит після таймауту — не дублюємо рядок
    const ids = sheet.getRange(2, 1, Math.max(sheet.getLastRow() - 1, 1), 1).getValues().flat();
    const existing = ids.indexOf(lead.id);
    if (existing !== -1) {
      return json_({ ok: true, row: existing + 2, existed: true });
    }

    sheet.appendRow([
      lead.id,
      new Date(lead.created_at),
      lead.name,
      "'" + (lead.phone || ''),   // апостроф, щоб таблиця не з'їла "+"
      lead.email,
      lead.message,
      lead.form,
      lead.page,
      lead.utm_source,
      lead.utm_medium,
      lead.utm_campaign,
      lead.duplicate ? 'так' : '',
      'Нова',
    ]);

    const row = sheet.getLastRow();
    if (lead.duplicate) {
      sheet.getRange(row, 1, 1, HEADERS.length).setBackground('#fff4cc');
    }
    return json_({ ok: true, row: row });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  } finally {
    lock.releaseLock();
  }
}

function json_(data) {
  return ContentService.createTextOutput(JSON.stringify(data)).setMimeType(ContentService.MimeType.JSON);
}
