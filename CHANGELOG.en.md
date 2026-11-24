# What's new in Nodus

What each version brings, newest first. To update, click “Update” when Nodus tells you there's a new version: your data is kept. The versions before 1.10, when Nodus spoke only Spanish, are described in [CHANGELOG.md](CHANGELOG.md).

## 1.12.0

- Screens that answer a question show the answer at the top, large and on its own, like the net worth on Home: an account's balance, what's saved toward a goal, a payee's or tag's total, and what recurring payments cost per month. The other figures go below, in boxes that all look alike, so your eye lands on what matters first.
- Deleting an account, a payee or a tag is in the “⋯” menu at the top of its page, as with goals, instead of the red card that sat at the foot. Nodus still asks first and says what goes with it.
- Categories shows how much each one added up to in the period you choose, from the largest down, with a bar of how much it weighs in total expenses or income. Subcategories go under their category, which adds them all up. A search at the top finds a category by its name.
- Each category has its own page, like accounts and payees: a double click in Categories opens it, as in Payees. It shows how much it added up to over the last 12 months, this month (with the change from the previous month, as on Home) and on average per month, a bar for each month of the last year (a click on a month opens its transactions), its subcategories or the category it sits in, and all its transactions. “Add transaction” from there starts with the category already chosen.
- “Merge with…” joins two categories that are the same: the transactions, recurring payments and payees that had it by default move to the one you choose, and the other is deleted. If the one that stays had no budget, it takes the other's. As when merging payees, the notice offers “Undo” (or Ctrl+Z), and Nodus also saves a copy of your data first.
- In Categories, each one has its check box, as in Payees: choose several and merge or delete them together, with a single confirmation.
- In Categories, each category forms a group with its subcategories, set apart from the next by a thin line. The arrow on its left hides the subcategories and shows them again; folded, the category says how many it has and its amount still adds them up. Nodus remembers what you folded, and a search shows the subcategory it finds even if its group is folded.
- The page of a category with subcategories goes from the whole to each part: every bar of “Month by month” is split by subcategory, as in Analysis, and the “By subcategory” card shows how much each one added up to over the last 12 months and what share of the total it is; a click opens its page. What sits in the category with no subcategory has a part of its own. When a subcategory has its category's color, the chart uses a lighter or darker shade to tell them apart.
- Budgets answers first how much you can still spend: at the top, in large type, what's left across all your budgets (or how far over you are), how much that is per day until the end of the month and a bar for the month with today's mark. Below it, only when it happens, which budget went over and how much you spent in categories without a limit, which doesn't come out of what's left; a click brings the “No budget” card up and highlights it for a moment. Rows are cleaner: the name, what's left and the bar; the “% used” shows on hover. A click anywhere on the row, the name or the bar, opens the category, in Budgets and on Home (the bar used to need a double click).
- Month bars show the hand when a click opens that month's transactions, in Analysis and on a category's page; a month with no transactions doesn't. On Home, a month of “Cash flow” now opens its transactions too.
- In a short window, the page of a category, a payee, a tag or a goal scrolls like an account's, instead of squashing the chart and the transactions to fit.
- In a narrow window, or with Help open, the figure boxes move onto a second row instead of squeezing all three together: in Analysis, Budgets, Recurring and Home's “Cash flow”, as an account's page already did. In Analysis, “By category” and “By payee” stack when they don't fit side by side.
- In Categories, the total of “Expenses” and “Income” sits under its card's title, like a figure in a box, instead of standing alone on the right.
- A click always leads to the same place: a category, payee or tag opens its page from Home, Analysis or Budgets (it used to open Transactions), and a month's bar opens its transactions. Every row that leads to another page lights up under the mouse, shows the hand and ends in “›”, as accounts do. In Categories, Payees and Tags, where a click chooses, a double click opens.
- The page of a category, payee or tag says when its total is from: what it added up to over the last 12 months, and how many transactions it had in them. All its transactions are still below.
- Payees and Tags have the same period picker as Categories: each list shows how much each one added up to in the period you choose, starting from the current month.

## 1.11.0 — 2026-11-21

- Nodus comes to Linux as an AppImage: a single file that opens with a double click on almost any distribution, with nothing to install. It shows up in the applications menu, can open when you sign in and updates itself, as on Windows.
- Nodus has a typeface of its own, Source Sans 3, and looks the same on any computer. It's narrower than before, so lists show more text before cutting it with “…”, like each transaction's description. The hints under each option and the titles of the cards grew a little and are easier to read.
- On Home, Help opens on the list of topics, so you see at once everything it explains. On the other screens it still opens on the topic of that screen.

## 1.10.0 — 2026-11-18

- Nodus speaks English. Choose the language in Settings, under “Language”; it applies when Nodus restarts. Amounts and dates change along with the text: in English they're written “$1,234.56” and “11/18/2026”. The first time, Nodus opens in your Windows language; if you were already using it, it stays in Spanish.
- When you export to CSV, the column names and the separator follow the language, so the file opens correctly in your Excel.
- Fix: the Categories and Tags icons were swapped. Tags now shows a tag, and Categories the “#”.
