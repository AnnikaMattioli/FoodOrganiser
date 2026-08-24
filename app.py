from flask import Flask, redirect, render_template, request, url_for

import food_organiser as food


app = Flask(__name__)


def get_connection():
    connection = food.connect_database()
    food.setup_database(connection)
    return connection


def parse_ingredients(prefix="ingredient"):
    names = request.form.getlist(f"{prefix}_name")
    amounts = request.form.getlist(f"{prefix}_amount")
    units = request.form.getlist(f"{prefix}_unit")
    shopping_flags = request.form.getlist(f"{prefix}_shopping")
    ingredients = []

    if not shopping_flags:
        shopping_flags = ["yes"] * len(names)
    for name, amount, unit, shopping_flag in zip(names, amounts, units, shopping_flags):
        name = food.normalise_name(name)
        unit = food.normalise_unit(unit)
        if not name or not amount:
            continue
        try:
            amount_value = float(amount)
        except ValueError:
            continue
        amount_value, unit = food.to_base_amount(amount_value, unit)
        ingredients.append({
            "name": name,
            "amount": amount_value,
            "unit": unit,
            "include_in_shopping": shopping_flag != "no",
        })

    return ingredients


@app.route("/")
def dashboard():
    connection = get_connection()
    cupboard = food.get_cupboard(connection)
    recipes = food.get_recipes(connection)
    connection.close()
    return render_template(
        "dashboard.html",
        cupboard_count=len(cupboard),
        recipe_count=len(recipes),
    )


@app.route("/cupboard", methods=["GET", "POST"])
def cupboard():
    connection = get_connection()
    if request.method == "POST":
        name = food.normalise_name(request.form["name"])
        amount = float(request.form["amount"])
        unit = food.normalise_unit(request.form["unit"])
        category = food.normalise_category(request.form.get("category", "Other"))
        amount, unit = food.to_base_amount(amount, unit)
        action = request.form.get("action")

        if action == "use":
            food.reduce_cupboard_item(connection, name, amount, unit)
        else:
            food.upsert_cupboard_item(connection, name, amount, unit, category)

        connection.close()
        return redirect(url_for("cupboard"))

    items = food.get_cupboard(connection)
    grouped_items = food.group_cupboard_by_category(items)
    connection.close()
    return render_template(
        "cupboard.html",
        items=items,
        grouped_items=grouped_items,
        categories=food.CUPBOARD_CATEGORIES,
        format_amount=food.format_amount,
    )


@app.route("/recipes")
@app.route("/recipe-book")
def recipes():
    connection = get_connection()
    all_recipes = food.get_recipes(connection)
    connection.close()
    return render_template("recipes.html", recipes=all_recipes, format_amount=food.format_amount)


@app.route("/recipes/new", methods=["GET", "POST"])
def new_recipe():
    if request.method == "POST":
        recipe_name = food.normalise_name(request.form["recipe_name"])
        instructions = request.form.get("instructions", "")
        ingredients = parse_ingredients()
        if recipe_name and ingredients:
            connection = get_connection()
            if not food.recipe_exists(connection, recipe_name):
                food.save_recipe(
                    connection,
                    recipe_name,
                    ingredients,
                    instructions,
                    request.form.get("yield_text", ""),
                    request.form.get("prep_time", ""),
                    request.form.get("cook_time", ""),
                )
            connection.close()
        return redirect(url_for("recipes"))

    return render_template(
        "recipe_form.html",
        recipe_name="",
        ingredients=[],
        instructions="",
        yield_text="",
        prep_time="",
        cook_time="",
        mode="Add",
    )


@app.route("/recipes/<path:recipe_name>")
def recipe_detail(recipe_name):
    recipe_name = food.normalise_name(recipe_name)
    connection = get_connection()
    recipe = food.get_recipes(connection).get(recipe_name)
    connection.close()
    if recipe is None:
        return redirect(url_for("recipes"))
    return render_template(
        "recipe_detail.html",
        recipe_name=recipe_name,
        recipe=recipe,
        format_amount=food.format_amount,
    )


@app.route("/recipes/<path:recipe_name>/edit", methods=["GET", "POST"])
def edit_recipe(recipe_name):
    recipe_name = food.normalise_name(recipe_name)
    connection = get_connection()
    recipes = food.get_recipes(connection)
    recipe = recipes.get(recipe_name)

    if recipe is None:
        connection.close()
        return redirect(url_for("recipes"))

    if request.method == "POST":
        ingredients = parse_ingredients()
        if ingredients:
            food.replace_recipe_ingredients(connection, recipe_name, ingredients)
            food.update_recipe_instructions(
                connection,
                recipe_name,
                request.form.get("instructions", ""),
            )
            food.update_recipe_details(
                connection,
                recipe_name,
                request.form.get("yield_text", ""),
                request.form.get("prep_time", ""),
                request.form.get("cook_time", ""),
            )
        connection.close()
        return redirect(url_for("recipe_detail", recipe_name=recipe_name))

    connection.close()
    return render_template(
        "recipe_form.html",
        recipe_name=recipe_name,
        ingredients=recipe["ingredients"],
        instructions=recipe["instructions"],
        yield_text=recipe["yield"],
        prep_time=recipe["prep_time"],
        cook_time=recipe["cook_time"],
        mode="Edit",
    )


@app.route("/recipes/<path:recipe_name>/delete", methods=["POST"])
def delete_recipe(recipe_name):
    recipe_name = food.normalise_name(recipe_name)
    connection = get_connection()
    food.delete_recipe_from_database(connection, recipe_name)
    connection.close()
    return redirect(url_for("recipes"))


@app.route("/planner", methods=["GET", "POST"])
def planner():
    connection = get_connection()
    recipes = food.get_recipes(connection)

    if request.method == "POST":
        plan = {}
        for day in food.DAYS:
            plan[day] = {}
            for meal in food.MEALS:
                recipe_name = food.normalise_name(request.form.get(f"{day}_{meal}", ""))
                plan[day][meal] = recipe_name if recipe_name in recipes else None

        required = food.ingredients_for_plan(plan, recipes)
        shopping = food.create_shopping_list(required, food.get_cupboard(connection))
        for extra in parse_ingredients(prefix="extra"):
            food.add_amount(shopping, extra["name"], extra["amount"], extra["unit"])

        copyable = food.copyable_shopping_list(connection, shopping)
        shopping_rows = []
        for name in sorted(shopping):
            item = shopping[name]
            shopping_rows.append(
                {
                    "name": name,
                    "text": food.format_shopping_item(
                        connection,
                        name,
                        item["amount"],
                        item["unit"],
                    ),
                }
            )

        connection.close()
        return render_template(
            "shopping_list.html",
            shopping_rows=shopping_rows,
            copyable=copyable,
        )

    connection.close()
    return render_template("planner.html", recipes=recipes, days=food.DAYS, meals=food.MEALS)


@app.route("/budget")
def budget():
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT shopping_date, total
        FROM shopping_history
        ORDER BY shopping_date DESC, id DESC
        LIMIT 10
        """
    ).fetchall()
    connection.close()
    latest = rows[0]["total"] if rows else None
    return render_template(
        "budget.html",
        rows=rows,
        latest=latest,
        format_money=food.format_money,
    )


if __name__ == "__main__":
    app.run(debug=True, port=5001)
