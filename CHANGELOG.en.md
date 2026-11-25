# What's new in Nodus

What each version brings, newest first. To update, click “Update” when Nodus tells you there's a new version: your data is kept. The versions before 1.10, when Nodus spoke only Spanish, are described in [CHANGELOG.md](CHANGELOG.md).

## 1.12.1 — 2026-11-25

- Fix: if Nodus could not check for a new version, for instance because GitHub was getting too many requests from your connection, it did not try again until the next time you opened it, and the update notice never came. Now it tries again on its own a while later and, while it stays open, checks every six hours.

## 1.12.0 — 2026-11-25

- Recording a transaction is quicker. The form fills in from top to bottom, with a larger amount, and an amount can be a calculation, such as 1,500+2,300 or 36000/3: you see the result as you type. Under the account you see its balance and how it ends up, and “Save and add another” (Ctrl+Enter) leaves the form ready for the next one. For what repeats, “Duplicate” copies a transaction and Ctrl+K offers “Repeat the last expense”.
- Each category has its page, like accounts: how much it added up to over the last year, month by month and by subcategory, with all its transactions. Categories shows how much each one added up to in the period you choose, with subcategories that fold and a search box, and “Merge with…” joins two categories that are the same.
- Budgets answers first how much you can still spend this month, and how much that is per day. Goals shows each goal as a card with what you saved, its bar and your pace.
- An account you keep but that isn't yours, such as a shared one, can stay out of your net worth with “Leave out of my net worth”: you keep it up to date, but it doesn't add to your totals or to your income and spending.
- Transactions reads better: each row says what it was, its category and its amount, always in the same column. A click on a column's title sorts by it, and a line above the list says what you are looking at and what it adds up to. Payees and Tags also sort by column and choose the period, and Payees separates those you pay from those who pay you.
- The interface looks more even and clearer: each screen shows what matters first, in large type; a click on a category, a payee or a tag always takes you to its page; and lists, charts and buttons look the same everywhere and fit a narrow window or one with Help open.
- Nodus can be used entirely with the keyboard: Ctrl+K finds any page, account or action, and there are shortcuts to record (Ctrl+N), search (Ctrl+F), go to each page (Ctrl+1 to Ctrl+9) and hide the amounts (Ctrl+H). It is also easier to use with a screen reader.
- Fix: in a narrow window, headers, buttons and tables no longer get cut off; a button no longer stays highlighted without touching the keyboard; hiding the amounts no longer moves the net worth chart; and “Last transaction” no longer shows an installment still to come.

## 1.11.0 — 2026-11-21

- Nodus comes to Linux as an AppImage: a single file that opens with a double click on almost any distribution, with nothing to install. It shows up in the applications menu, can open when you sign in and updates itself, as on Windows.
- Nodus has a typeface of its own, Source Sans 3, and looks the same on any computer. It's narrower than before, so lists show more text before cutting it with “…”, like each transaction's description. The hints under each option and the titles of the cards grew a little and are easier to read.
- On Home, Help opens on the list of topics, so you see at once everything it explains. On the other screens it still opens on the topic of that screen.

## 1.10.0 — 2026-11-18

- Nodus speaks English. Choose the language in Settings, under “Language”; it applies when Nodus restarts. Amounts and dates change along with the text: in English they're written “$1,234.56” and “11/18/2026”. The first time, Nodus opens in your Windows language; if you were already using it, it stays in Spanish.
- When you export to CSV, the column names and the separator follow the language, so the file opens correctly in your Excel.
- Fix: the Categories and Tags icons were swapped. Tags now shows a tag, and Categories the “#”.
