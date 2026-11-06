<div align="center">

<img src="src/nodus/ui/icons/logo.svg" width="88" alt="Nodus logo">

# Nodus

**Your finances, on your computer.**

Personal finance with the look of a modern app and the privacy of a file that is yours alone.<br>
No cloud, no accounts, no subscriptions.

**English** · [Español](README.es.md)

[![Latest release](https://img.shields.io/github/v/release/germanricco/Nodus)](https://github.com/germanricco/Nodus/releases/latest)
[![MIT License](https://img.shields.io/github/license/germanricco/Nodus)](LICENSE)
[![Windows 10 and 11](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D4)](https://github.com/germanricco/Nodus/releases/latest)

### [Download for Windows](https://github.com/germanricco/Nodus/releases/latest)

</div>

<!-- Main screenshot (v1.0): copy the `scripts/screenshot.py --demo` captures to docs/images/ and remove this comment.
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/dashboard-full-dark.png">
  <img src="docs/images/dashboard-full-light.png" alt="The Nodus dashboard: net worth, upcoming payments, spending by category and budgets">
</picture>
-->

> The app's interface is in Spanish: Nodus was built for people in Argentina who keep their money in both pesos and US dollars.

## Why Nodus

Personal finance apps that look good tend to live in the cloud: they ask you to sign up, charge a subscription and keep your financial history on someone else's servers. The ones that run on your own computer, on the other hand, often feel like software from another era. Nodus aims for the missing middle ground: a polished, fluid interface that runs entirely on your machine, with all your data in a single file you can copy, back up or move whenever you like.

It was born for people who manage money in pesos and dollars at the same time. Each account has its own currency, dollar purchases record both what went out and what came in, and your net worth shows in either currency at the exchange rate you choose. *Nodus* is Latin for "node", the point where lines meet, and that is the idea: your computer is the only place where your financial data comes together.

## What you can do

### See where you stand at a glance
The dashboard answers the usual questions: how much you have, how the month is going and where the money went. It shows how your net worth evolves, your upcoming payments, spending by category against the previous period, cash flow month by month and your budgets. Pick a period (this month, the last 3, 6 or 12 months, the year), and click a category to see its transactions.

<!-- Screenshot (v1.0): docs/images/dashboard-light.png | docs/images/dashboard-dark.png -->

### Keep accounts in pesos and dollars
Add every place where you keep money, from your bank and cash to dollar savings or a credit card, and balances are always computed from your transactions. When you buy dollars, Nodus stores both amounts and shows the rate you actually got. Today's exchange rate can be fetched automatically or entered by hand.

<!-- Screenshot (v1.0): docs/images/accounts-light.png | docs/images/accounts-dark.png -->

### Record and find your transactions
One form covers expenses, income and transfers, and it starts on the account you used last. The list filters by period, account, category, payee, type or text, and whatever you see exports to a file that opens in Excel.

<!-- Screenshot (v1.0): docs/images/transactions-light.png | docs/images/transactions-dark.png -->

### Know who your money goes to
Each expense or income can say who you paid or who paid you: the supermarket, the power company, your employer. Type a few letters to pick one, or a new name to add it, and Nodus fills in the category you usually use with it. The Payees page shows how many transactions and how much money went to or came from each one, so a question like "how much do I spend at the supermarket?" takes one click. Duplicates such as "Coto" and "Coto Online" can be merged into one.

<!-- Screenshot (v1.0): docs/images/payees-light.png | docs/images/payees-dark.png -->

### Never forget what you pay every month
Enter rent, utilities or subscriptions once, and Nodus shows what they add up to per month, what is due soon and what is overdue. Paying one takes two clicks: the expense is recorded and the charge moves on to its next date.

<!-- Screenshot (v1.0): docs/images/recurring-light.png | docs/images/recurring-dark.png -->

### Put a limit on your spending
Set a monthly budget for the categories you want to watch and see how much you have spent and how much is left. The bar turns amber when you spend faster than the month goes by and red when you go over, early enough to slow down. To choose a limit, Nodus suggests your average of the last few months.

<!-- Screenshot (v1.0): docs/images/budgets-light.png | docs/images/budgets-dark.png -->

### Hear about what matters
A bell gathers what needs your attention: a payment coming due, a budget passed, a stale exchange rate or a new version to install. Nodus also backs up your data every day, and you can restore any copy from Settings. Everything works in light or dark mode.

<!-- Screenshot (v1.0): docs/images/notifications-light.png | docs/images/notifications-dark.png -->

## Your data stays yours

Everything lives in one file on your computer, `%APPDATA%\Nodus\nodus.db`, with the daily backups next to it in `%APPDATA%\Nodus\backups`. Updating or uninstalling Nodus never touches it. The app only goes online for two things, and you can turn both off: checking GitHub for a new version, without sending any of your data, and fetching the dollar rate from [DolarApi](https://dolarapi.com) if you chose an automatic one.

## Download and install

Nodus runs on **64-bit Windows 10 and 11**.

1. Download `Nodus-Setup-<version>.exe` from the [latest release](https://github.com/germanricco/Nodus/releases/latest).
2. Open it and follow the wizard. It installs for your user only, without administrator rights, and shows up in the Start menu.
3. If Windows says "Windows protected your PC", click "More info" and then "Run anyway". The warning appears because the installer has no commercial code-signing certificate, which costs a yearly fee. Every installer is built automatically on GitHub from the code in this repository.

To update, install the new version over the old one: your data is kept. Nodus lets you know when a new version is out.

## Roadmap

Nodus grows in small, stable releases. **v0.7** already covers accounts, transactions, dollar exchange rates, the dashboard, recurring charges, budgets, payees, backups and export. Coming next:

- **Analysis:** income, spending and net worth over time, in detail.
- **Refunds and tags:** expenses that get paid back, and tags such as "Vacation 2026".
- **Goals and account groups:** saving for something specific, and grouping banks, investments and cash.

## Technology

Nodus is written in **Python**. The interface uses **PySide6**, the official Qt for Python, which gives fast native apps without shipping a browser. Data is stored in **SQLite**, a single-file database that needs no server. The installer is built with PyInstaller and Inno Setup.

## Contributing

Ideas and bug reports are welcome in [Issues](https://github.com/germanricco/Nodus/issues). To run Nodus from source, run the tests or build the installer, see [CONTRIBUTING.md](CONTRIBUTING.md) (in Spanish).

## Acknowledgements

Nodus's features and design are inspired by [MoneyMatter](https://github.com/letehaha/moneymatter), an open-source personal finance web app. Nodus reuses none of its code: it reimplements its ideas as a local desktop application.

## License

Nodus is free software under the [MIT License](LICENSE).

Made by [German Ricco](https://github.com/germanricco).
