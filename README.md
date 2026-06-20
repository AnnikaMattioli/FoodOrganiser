# Food Organiser

A beginner-friendly terminal app for planning uni meals, tracking cupboard ingredients, and creating a shopping list.

## What it does

- Tracks exact cupboard amounts, like `flour: 500 g` or `cereal: 1 box`.
- Lets you save recipes manually.
- Lets you view, edit, and delete saved recipes.
- Plans 7 days of lunch and dinner.
- Lets you type `n/a` for meals where you are going out or skipping food at home.
- Shows what percentage of a recipe's ingredients you already have.
- Creates a combined shopping list and rounds some items to supermarket-friendly amounts.
- Asks for extra one-off shopping items, like protein bars or soda, before showing the final list.
- Shows a clean copyable shopping list that can be pasted into Notes.
- Asks whether you need to review or change the shopping list before finishing.
- Has optional price estimates for budget tracking.
- Shows weekly, monthly, and yearly budget projections from saved shopping totals.
- Saves confirmed shopping totals so you can look back at recent spending.
- Lets you update price estimates for your usual supermarket amounts.

## Run it

For the web app:

```bash
python3 app.py
```

Then open:

```text
http://127.0.0.1:5001
```

For the original terminal app:

```bash
python3 food_organiser.py
```

The app stores data in a SQLite database at:

```text
data/food_organiser.db
```

SQLite is a real database, but it is still beginner-friendly because it lives in one local file.
