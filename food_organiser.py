import json
import math
import sqlite3
from datetime import date
from pathlib import Path


DATA_DIR = Path("data")
DB_FILE = DATA_DIR / "food_organiser.db"
OLD_CUPBOARD_FILE = DATA_DIR / "cupboard.json"
OLD_RECIPES_FILE = DATA_DIR / "recipes.json"

DAYS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

MEALS = ["lunch", "dinner"]

UNIT_ALIASES = {
    "gram": "g",
    "grams": "g",
    "g": "g",
    "kg": "kg",
    "kilogram": "kg",
    "kilograms": "kg",
    "ml": "ml",
    "millilitre": "ml",
    "millilitres": "ml",
    "l": "l",
    "litre": "l",
    "litres": "l",
    "each": "each",
    "item": "each",
    "items": "each",
    "punnet": "punnet",
    "punnets": "punnet",
    "box": "box",
    "boxes": "box",
    "bag": "bag",
    "bags": "bag",
    "tin": "tin",
    "tins": "tin",
    "can": "can",
    "cans": "can",
}

BUYING_AMOUNTS = {
    ("flour", "g"): 1000,
    ("sugar", "g"): 1000,
    ("rice", "g"): 1000,
    ("pasta", "g"): 500,
    ("butter", "g"): 250,
    ("cheese", "g"): 400,
    ("milk", "ml"): 1000,
    ("oil", "ml"): 500,
    ("cereal", "g"): 500,
    ("strawberries", "g"): 400,
    ("blueberries", "g"): 150,
    ("protein bar", "each"): 1,
    ("soda", "ml"): 2000,
}

PACKAGE_NAMES = {
    ("flour", "g"): "kg bag",
    ("sugar", "g"): "kg bag",
    ("rice", "g"): "kg bag",
    ("pasta", "g"): "bag",
    ("butter", "g"): "block",
    ("cheese", "g"): "pack",
    ("milk", "ml"): "litre bottle",
    ("oil", "ml"): "bottle",
    ("cereal", "g"): "box",
    ("strawberries", "g"): "punnet",
    ("blueberries", "g"): "punnet",
    ("protein bar", "each"): "bar",
    ("soda", "ml"): "bottle",
}

DEFAULT_PRICES = {
    ("flour", "g"): (1000, 0.85),
    ("sugar", "g"): (1000, 1.09),
    ("rice", "g"): (1000, 1.55),
    ("pasta", "g"): (500, 0.75),
    ("butter", "g"): (250, 1.99),
    ("cheese", "g"): (400, 2.75),
    ("milk", "ml"): (1000, 1.20),
    ("oil", "ml"): (500, 1.85),
    ("cereal", "g"): (500, 2.25),
    ("strawberries", "g"): (400, 2.25),
    ("blueberries", "g"): (150, 2.00),
    ("protein bar", "each"): (1, 1.25),
    ("soda", "ml"): (2000, 1.50),
}


def connect_database():
    DATA_DIR.mkdir(exist_ok=True)
    connection = sqlite3.connect(DB_FILE)
    connection.row_factory = sqlite3.Row
    return connection


def setup_database(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS cupboard_items (
            name TEXT PRIMARY KEY,
            amount REAL NOT NULL,
            unit TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS recipe_ingredients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            amount REAL NOT NULL,
            unit TEXT NOT NULL,
            FOREIGN KEY (recipe_id) REFERENCES recipes (id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS price_estimates (
            name TEXT NOT NULL,
            unit TEXT NOT NULL,
            package_amount REAL NOT NULL,
            package_price REAL NOT NULL,
            PRIMARY KEY (name, unit)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS shopping_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shopping_date TEXT NOT NULL,
            total REAL NOT NULL
        )
        """
    )
    connection.commit()
    seed_default_prices(connection)
    migrate_old_json_data(connection)


def seed_default_prices(connection):
    for (name, unit), (package_amount, package_price) in DEFAULT_PRICES.items():
        connection.execute(
            """
            INSERT OR IGNORE INTO price_estimates
                (name, unit, package_amount, package_price)
            VALUES (?, ?, ?, ?)
            """,
            (name, unit, package_amount, package_price),
        )
    connection.commit()


def migrate_old_json_data(connection):
    if OLD_CUPBOARD_FILE.exists():
        with OLD_CUPBOARD_FILE.open("r", encoding="utf-8") as file:
            cupboard = json.load(file)
        for name, item in cupboard.items():
            upsert_cupboard_item(connection, name, item["amount"], item["unit"])

    if OLD_RECIPES_FILE.exists():
        with OLD_RECIPES_FILE.open("r", encoding="utf-8") as file:
            recipes = json.load(file)
        for recipe_name, recipe in recipes.items():
            if recipe_exists(connection, recipe_name):
                continue
            save_recipe(connection, recipe_name, recipe["ingredients"])


def normalise_name(name):
    return name.strip().lower()


def normalise_unit(unit):
    cleaned = unit.strip().lower()
    return UNIT_ALIASES.get(cleaned, cleaned)


def to_base_amount(amount, unit):
    if unit == "kg":
        return amount * 1000, "g"
    if unit == "l":
        return amount * 1000, "ml"
    return amount, unit


def format_amount(amount, unit):
    if unit == "g" and amount >= 1000 and amount % 1000 == 0:
        return f"{int(amount / 1000)} kg"
    if unit == "ml" and amount >= 1000 and amount % 1000 == 0:
        return f"{int(amount / 1000)} l"
    if amount == int(amount):
        return f"{int(amount)} {unit}"
    return f"{amount:.2f} {unit}"


def format_money(amount):
    return f"£{amount:.2f}"


def input_number(prompt):
    while True:
        raw = input(prompt).strip()
        try:
            value = float(raw)
            if value < 0:
                print("Please enter zero or a positive number.")
                continue
            return value
        except ValueError:
            print("Please enter a number, for example 500 or 1.5.")


def input_whole_number(prompt):
    while True:
        raw = input(prompt).strip()
        try:
            value = int(raw)
            if value < 1:
                print("Please enter a positive whole number.")
                continue
            return value
        except ValueError:
            print("Please enter a whole number, for example 1 or 2.")


def ask_yes_no(prompt):
    while True:
        answer = input(f"{prompt} (y/n): ").strip().lower()
        if answer in ["y", "yes"]:
            return True
        if answer in ["n", "no"]:
            return False
        print("Please type y or n.")


def add_amount(store, name, amount, unit):
    if name not in store:
        store[name] = {"amount": 0, "unit": unit}

    if store[name]["unit"] != unit:
        print(
            f"Unit mismatch for {name}. Existing unit is {store[name]['unit']}, "
            f"so I could not combine it with {unit}."
        )
        return False

    store[name]["amount"] += amount
    return True


def enter_ingredient():
    name = normalise_name(input("Ingredient name: "))
    amount = input_number("Amount: ")
    unit = normalise_unit(input("Unit, for example g, kg, ml, l, each, punnet, box: "))
    amount, unit = to_base_amount(amount, unit)
    return name, amount, unit


def get_cupboard(connection):
    rows = connection.execute(
        "SELECT name, amount, unit FROM cupboard_items ORDER BY name"
    ).fetchall()
    return {
        row["name"]: {"amount": row["amount"], "unit": row["unit"]}
        for row in rows
    }


def upsert_cupboard_item(connection, name, amount, unit):
    existing = connection.execute(
        "SELECT amount, unit FROM cupboard_items WHERE name = ?",
        (name,),
    ).fetchone()

    if existing and existing["unit"] != unit:
        print(
            f"Unit mismatch for {name}. Existing unit is {existing['unit']}, "
            f"so I could not combine it with {unit}."
        )
        return False

    if existing:
        connection.execute(
            "UPDATE cupboard_items SET amount = amount + ? WHERE name = ?",
            (amount, name),
        )
    else:
        connection.execute(
            "INSERT INTO cupboard_items (name, amount, unit) VALUES (?, ?, ?)",
            (name, amount, unit),
        )

    connection.commit()
    return True


def reduce_cupboard_item(connection, name, amount, unit):
    existing = connection.execute(
        "SELECT amount, unit FROM cupboard_items WHERE name = ?",
        (name,),
    ).fetchone()

    if not existing:
        return
    if existing["unit"] != unit:
        return

    new_amount = max(0, existing["amount"] - amount)
    connection.execute(
        "UPDATE cupboard_items SET amount = ? WHERE name = ?",
        (new_amount, name),
    )
    connection.commit()


def view_cupboard(connection):
    cupboard = get_cupboard(connection)
    print("\nYour cupboard")
    print("-------------")
    if not cupboard:
        print("No ingredients stored yet.")
        return

    for name, item in cupboard.items():
        print(f"{name}: {format_amount(item['amount'], item['unit'])}")


def add_to_cupboard(connection):
    print("\nAdd something to your cupboard")
    name, amount, unit = enter_ingredient()
    if upsert_cupboard_item(connection, name, amount, unit):
        print(f"Added {format_amount(amount, unit)} of {name}.")


def use_from_cupboard(connection):
    print("\nUse something from your cupboard")
    name, amount, unit = enter_ingredient()
    reduce_cupboard_item(connection, name, amount, unit)
    print("Cupboard updated.")


def recipe_exists(connection, recipe_name):
    row = connection.execute(
        "SELECT id FROM recipes WHERE name = ?",
        (recipe_name,),
    ).fetchone()
    return row is not None


def get_recipes(connection):
    rows = connection.execute("SELECT id, name FROM recipes ORDER BY name").fetchall()
    recipes = {}

    for row in rows:
        ingredient_rows = connection.execute(
            """
            SELECT name, amount, unit
            FROM recipe_ingredients
            WHERE recipe_id = ?
            ORDER BY id
            """,
            (row["id"],),
        ).fetchall()
        recipes[row["name"]] = {
            "ingredients": [
                {
                    "name": ingredient["name"],
                    "amount": ingredient["amount"],
                    "unit": ingredient["unit"],
                }
                for ingredient in ingredient_rows
            ]
        }

    return recipes


def save_recipe(connection, recipe_name, ingredients):
    cursor = connection.execute(
        "INSERT INTO recipes (name) VALUES (?)",
        (recipe_name,),
    )
    recipe_id = cursor.lastrowid

    for ingredient in ingredients:
        connection.execute(
            """
            INSERT INTO recipe_ingredients (recipe_id, name, amount, unit)
            VALUES (?, ?, ?, ?)
            """,
            (
                recipe_id,
                ingredient["name"],
                ingredient["amount"],
                ingredient["unit"],
            ),
        )

    connection.commit()


def replace_recipe_ingredients(connection, recipe_name, ingredients):
    recipe = connection.execute(
        "SELECT id FROM recipes WHERE name = ?",
        (recipe_name,),
    ).fetchone()
    if not recipe:
        return

    connection.execute(
        "DELETE FROM recipe_ingredients WHERE recipe_id = ?",
        (recipe["id"],),
    )
    for ingredient in ingredients:
        connection.execute(
            """
            INSERT INTO recipe_ingredients (recipe_id, name, amount, unit)
            VALUES (?, ?, ?, ?)
            """,
            (
                recipe["id"],
                ingredient["name"],
                ingredient["amount"],
                ingredient["unit"],
            ),
        )
    connection.commit()


def delete_recipe_from_database(connection, recipe_name):
    connection.execute("DELETE FROM recipes WHERE name = ?", (recipe_name,))
    connection.commit()


def recipe_coverage(recipe, cupboard):
    total_ingredients = len(recipe["ingredients"])
    if total_ingredients == 0:
        return 0

    covered = 0
    for ingredient in recipe["ingredients"]:
        name = ingredient["name"]
        needed = ingredient["amount"]
        unit = ingredient["unit"]
        cupboard_item = cupboard.get(name)
        if cupboard_item and cupboard_item["unit"] == unit and cupboard_item["amount"] >= needed:
            covered += 1

    return round((covered / total_ingredients) * 100)


def show_recipe_draft(recipe_name, ingredients):
    print(f"\n{recipe_name}")
    print("-" * len(recipe_name))
    if not ingredients:
        print("No ingredients yet.")
        return

    for index, ingredient in enumerate(ingredients, start=1):
        print(
            f"{index}. {ingredient['name']} - "
            f"{format_amount(ingredient['amount'], ingredient['unit'])}"
        )


def remove_ingredient_from_list(ingredients):
    if not ingredients:
        print("There are no ingredients to remove yet.")
        return

    number = input_whole_number("Ingredient number to remove: ")
    index = number - 1
    if 0 <= index < len(ingredients):
        removed = ingredients.pop(index)
        print(f"Removed {removed['name']}.")
    else:
        print("That ingredient number does not exist.")


def create_recipe(connection):
    print("\nCreate a recipe")
    recipe_name = normalise_name(input("Recipe name: "))
    if recipe_exists(connection, recipe_name):
        print("That recipe already exists. Use edit recipe if you want to change it.")
        return

    ingredients = []
    while True:
        show_recipe_draft(recipe_name, ingredients)
        print("\n1. Add ingredient")
        print("2. Remove ingredient")
        print("3. Save recipe")
        print("4. Cancel")
        choice = input("Choose an option: ").strip()

        if choice == "1":
            print("\nAdd an ingredient")
            name, amount, unit = enter_ingredient()
            ingredients.append({"name": name, "amount": amount, "unit": unit})
        elif choice == "2":
            remove_ingredient_from_list(ingredients)
        elif choice == "3":
            if not ingredients:
                print("Add at least one ingredient before saving.")
                continue
            recipe = {"ingredients": ingredients}
            coverage = recipe_coverage(recipe, get_cupboard(connection))
            print(f"\nYou already have enough of {coverage}% of this recipe's ingredients.")
            if ask_yes_no(f"Save '{recipe_name}' to your recipes"):
                save_recipe(connection, recipe_name, ingredients)
                print("Recipe saved.")
                return
        elif choice == "4":
            print("Recipe cancelled.")
            return
        else:
            print("Please choose a number from 1 to 4.")


def list_recipes(connection):
    recipes = get_recipes(connection)
    print("\nSaved recipes")
    print("-------------")
    if not recipes:
        print("No saved recipes yet.")
        return

    for recipe_name in recipes:
        print(f"- {recipe_name}")


def choose_existing_recipe(connection):
    recipes = get_recipes(connection)
    if not recipes:
        print("\nNo saved recipes yet.")
        return None, None

    list_recipes(connection)
    while True:
        recipe_name = normalise_name(input("Recipe name: "))
        if recipe_name in recipes:
            return recipe_name, recipes[recipe_name]
        print("That recipe is not saved yet. Type one of the recipe names above.")


def view_one_recipe(connection):
    print("\nView a recipe")
    recipe_name, recipe = choose_existing_recipe(connection)
    if recipe is None:
        return
    show_recipe_draft(recipe_name, recipe["ingredients"])


def edit_recipe(connection):
    print("\nEdit a recipe")
    recipe_name, recipe = choose_existing_recipe(connection)
    if recipe is None:
        return

    ingredients = recipe["ingredients"]
    while True:
        show_recipe_draft(recipe_name, ingredients)
        print("\n1. Add ingredient")
        print("2. Remove ingredient")
        print("3. Save changes")
        print("4. Cancel")
        choice = input("Choose an option: ").strip()

        if choice == "1":
            print("\nAdd an ingredient")
            name, amount, unit = enter_ingredient()
            ingredients.append({"name": name, "amount": amount, "unit": unit})
        elif choice == "2":
            remove_ingredient_from_list(ingredients)
        elif choice == "3":
            if not ingredients:
                print("A recipe needs at least one ingredient.")
                continue
            replace_recipe_ingredients(connection, recipe_name, ingredients)
            print("Recipe updated.")
            return
        elif choice == "4":
            print("Changes cancelled.")
            return
        else:
            print("Please choose a number from 1 to 4.")


def delete_recipe(connection):
    print("\nDelete a recipe")
    recipe_name, recipe = choose_existing_recipe(connection)
    if recipe is None:
        return

    show_recipe_draft(recipe_name, recipe["ingredients"])
    if ask_yes_no(f"Delete '{recipe_name}' permanently"):
        delete_recipe_from_database(connection, recipe_name)
        print("Recipe deleted.")
    else:
        print("Recipe kept.")


def recipe_menu(connection):
    while True:
        print("\nRecipes")
        print("=======")
        print("1. Add a new recipe")
        print("2. View all recipes")
        print("3. View one recipe")
        print("4. Edit a recipe")
        print("5. Delete a recipe")
        print("6. Back")
        choice = input("Choose an option: ").strip()

        if choice == "1":
            create_recipe(connection)
        elif choice == "2":
            list_recipes(connection)
        elif choice == "3":
            view_one_recipe(connection)
        elif choice == "4":
            edit_recipe(connection)
        elif choice == "5":
            delete_recipe(connection)
        elif choice == "6":
            return
        else:
            print("Please choose a number from 1 to 6.")


def choose_recipe(recipes, day, meal):
    while True:
        recipe_name = normalise_name(input(f"{day} {meal}: "))
        if recipe_name in ["n/a", "na", "none", "skip"]:
            return None
        if recipe_name in recipes:
            return recipe_name
        print("Type a saved recipe name, or n/a if you are going out or skipping it.")


def build_week_plan(connection):
    recipes = get_recipes(connection)
    if not recipes:
        print("\nYou need to save at least one recipe before planning a week.")
        return None

    print("\nPlan your week")
    print("Type the recipe name for each lunch and dinner, or n/a to skip a meal.")
    list_recipes(connection)

    plan = {}
    for day in DAYS:
        plan[day] = {}
        print(f"\n{day}")
        for meal in MEALS:
            plan[day][meal] = choose_recipe(recipes, day, meal)

    return plan


def ingredients_for_plan(plan, recipes):
    required = {}

    for day in DAYS:
        for meal in MEALS:
            recipe_name = plan[day][meal]
            if recipe_name is None:
                continue
            recipe = recipes[recipe_name]
            for ingredient in recipe["ingredients"]:
                add_amount(
                    required,
                    ingredient["name"],
                    ingredient["amount"],
                    ingredient["unit"],
                )

    return required


def create_shopping_list(required, cupboard):
    shopping = {}

    for name, needed_item in required.items():
        needed = needed_item["amount"]
        unit = needed_item["unit"]
        available = 0

        if name in cupboard and cupboard[name]["unit"] == unit:
            available = cupboard[name]["amount"]

        amount_to_buy = needed - available
        if amount_to_buy > 0:
            shopping[name] = {"amount": amount_to_buy, "unit": unit}

    return shopping


def add_extra_shopping_items(shopping):
    if not ask_yes_no("\nDo you need to add any extra items, like protein bars or soda"):
        return

    while True:
        print("\nAdd an extra shopping item")
        name, amount, unit = enter_ingredient()
        add_amount(shopping, name, amount, unit)

        if not ask_yes_no("Add another extra item"):
            return


def remove_shopping_item(shopping):
    if not shopping:
        print("There is nothing on the shopping list to remove.")
        return

    names = sorted(shopping)
    print("\nRemove an item")
    for index, name in enumerate(names, start=1):
        item = shopping[name]
        print(f"{index}. {name} - {format_amount(item['amount'], item['unit'])}")

    number = input_whole_number("Item number to remove: ")
    index = number - 1
    if 0 <= index < len(names):
        removed = names[index]
        del shopping[removed]
        print(f"Removed {removed}.")
    else:
        print("That item number does not exist.")


def get_price_estimate(connection, name, unit):
    return connection.execute(
        """
        SELECT package_amount, package_price
        FROM price_estimates
        WHERE name = ? AND unit = ?
        """,
        (name, unit),
    ).fetchone()


def shopping_package_total(connection, name, amount, unit):
    price = get_price_estimate(connection, name, unit)
    package_size = BUYING_AMOUNTS.get((name, unit))

    if price:
        package_amount = price["package_amount"]
        packages = math.ceil(amount / package_amount)
        return packages, package_amount, packages * price["package_price"]

    if package_size:
        return math.ceil(amount / package_size), package_size, None

    return None, None, None


def shopping_buy_amount(connection, name, amount, unit):
    packages, package_amount, _ = shopping_package_total(connection, name, amount, unit)
    if packages and package_amount:
        return packages * package_amount
    return amount


def format_shopping_item(connection, name, amount, unit):
    packages, package_amount, _ = shopping_package_total(connection, name, amount, unit)
    package_name = PACKAGE_NAMES.get((name, unit), "pack")

    if packages and package_amount:
        total = packages * package_amount
        return (
            f"{name}: buy {packages} {package_name}"
            f" ({format_amount(total, unit)} total; need {format_amount(amount, unit)}"
            f")"
        )

    return f"{name}: buy {format_amount(amount, unit)}"


def copyable_shopping_list(connection, shopping):
    lines = ["Shopping list"]
    for name in sorted(shopping):
        item = shopping[name]
        buy_amount = shopping_buy_amount(
            connection,
            name,
            item["amount"],
            item["unit"],
        )
        lines.append(f"- {name}: {format_amount(buy_amount, item['unit'])}")
    return "\n".join(lines)


def estimate_shopping_total(connection, shopping):
    total = 0
    missing_prices = []

    for name, item in shopping.items():
        _, _, cost = shopping_package_total(connection, name, item["amount"], item["unit"])
        if cost is None:
            missing_prices.append(name)
        else:
            total += cost

    return total, missing_prices


def print_budget_projection(weekly_total):
    monthly_total = weekly_total * 52 / 12
    yearly_total = weekly_total * 52
    print("\nBudget projection")
    print("-----------------")
    print(f"Weekly: {format_money(weekly_total)}")
    print(f"Monthly average: {format_money(monthly_total)}")
    print(f"Yearly: {format_money(yearly_total)}")


def show_shopping_list(connection, shopping):
    print("\nShopping list")
    print("-------------")
    if not shopping:
        print("You already have everything for this week.")
        return

    for name in sorted(shopping):
        item = shopping[name]
        print(format_shopping_item(connection, name, item["amount"], item["unit"]))

    print("\nCopyable version for Notes")
    print("--------------------------")
    print(copyable_shopping_list(connection, shopping))


def save_shopping_history(connection, total):
    connection.execute(
        "INSERT INTO shopping_history (shopping_date, total) VALUES (?, ?)",
        (date.today().isoformat(), total),
    )
    connection.commit()


def add_shopping_to_cupboard(connection, shopping):
    if not shopping:
        return

    if not ask_yes_no("\nAdd this shopping list to your cupboard as bought food"):
        return

    total, _ = estimate_shopping_total(connection, shopping)
    for name, item in shopping.items():
        packages, package_amount, _ = shopping_package_total(
            connection,
            name,
            item["amount"],
            item["unit"],
        )
        amount = item["amount"]
        if packages and package_amount:
            amount = packages * package_amount
        upsert_cupboard_item(connection, name, amount, item["unit"])

    save_shopping_history(connection, total)
    print("Cupboard updated with shopping.")


def review_shopping_list(connection, shopping):
    while True:
        show_shopping_list(connection, shopping)
        if not ask_yes_no("\nDo you need to review or change this list before finishing"):
            return

        print("\nReview shopping list")
        print("1. Add another item")
        print("2. Remove an item")
        print("3. Show list again")
        print("4. Finish")
        choice = input("Choose an option: ").strip()

        if choice == "1":
            print("\nAdd another shopping item")
            name, amount, unit = enter_ingredient()
            add_amount(shopping, name, amount, unit)
        elif choice == "2":
            remove_shopping_item(shopping)
        elif choice == "3":
            continue
        elif choice == "4":
            return
        else:
            print("Please choose a number from 1 to 4.")


def view_budget(connection):
    rows = connection.execute(
        """
        SELECT shopping_date, total
        FROM shopping_history
        ORDER BY shopping_date DESC, id DESC
        LIMIT 10
        """
    ).fetchall()

    print("\nBudget")
    print("======")
    if not rows:
        print("No confirmed shopping trips yet.")
        print("Create a shopping list and add it to your cupboard to save a total.")
        return

    latest_total = rows[0]["total"]
    print_budget_projection(latest_total)
    print("\nRecent shopping totals")
    print("----------------------")
    for row in rows:
        print(f"{row['shopping_date']}: {format_money(row['total'])}")


def update_price_estimate(connection):
    print("\nAdd or update a price estimate")
    name, package_amount, unit = enter_ingredient()
    price = input_number("Price for that supermarket amount, in pounds: £")

    connection.execute(
        """
        INSERT INTO price_estimates (name, unit, package_amount, package_price)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(name, unit) DO UPDATE SET
            package_amount = excluded.package_amount,
            package_price = excluded.package_price
        """,
        (name, unit, package_amount, price),
    )
    connection.commit()
    print(f"Saved price estimate for {name}: {format_amount(package_amount, unit)} costs {format_money(price)}.")


def plan_week_and_shop(connection):
    plan = build_week_plan(connection)
    if plan is None:
        return

    recipes = get_recipes(connection)
    required = ingredients_for_plan(plan, recipes)
    shopping = create_shopping_list(required, get_cupboard(connection))
    add_extra_shopping_items(shopping)
    review_shopping_list(connection, shopping)
    add_shopping_to_cupboard(connection, shopping)


def main_menu():
    print("\nFood Organiser")
    print("==============")
    print("1. View cupboard")
    print("2. Add food to cupboard")
    print("3. Use food from cupboard")
    print("4. Recipes")
    print("5. Plan week and create shopping list")
    print("6. Add or update a price estimate")
    print("7. View budget")
    print("8. Quit")


def main():
    connection = connect_database()
    setup_database(connection)

    while True:
        main_menu()
        choice = input("Choose an option: ").strip()

        if choice == "1":
            view_cupboard(connection)
        elif choice == "2":
            add_to_cupboard(connection)
        elif choice == "3":
            use_from_cupboard(connection)
        elif choice == "4":
            recipe_menu(connection)
        elif choice == "5":
            plan_week_and_shop(connection)
        elif choice == "6":
            update_price_estimate(connection)
        elif choice == "7":
            view_budget(connection)
        elif choice == "8":
            print("Bye!")
            break
        else:
            print("Please choose a number from 1 to 8.")

    connection.close()


if __name__ == "__main__":
    main()
