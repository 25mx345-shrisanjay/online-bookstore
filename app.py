
from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import os

app = Flask(__name__)
DB = os.path.join(os.path.dirname(__file__), "bookstore.db")


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                price REAL NOT NULL,
                stock INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer TEXT NOT NULL,
                book_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending',
                FOREIGN KEY (book_id) REFERENCES books(id)
            )
        """)


@app.route("/")
def index():
    with get_db() as conn:
        books = conn.execute("SELECT * FROM books ORDER BY id DESC").fetchall()
    return render_template("index.html", books=books)


@app.route("/add", methods=["GET", "POST"])
def add_book():
    if request.method == "POST":
        title = request.form["title"].strip()
        author = request.form["author"].strip()
        price = float(request.form["price"])
        stock = int(request.form["stock"])

        if not title or not author or price < 0 or stock < 0:
            return "Invalid book details", 400

        with get_db() as conn:
            conn.execute(
                "INSERT INTO books (title, author, price, stock) VALUES (?, ?, ?, ?)",
                (title, author, price, stock)
            )
        return redirect(url_for("index"))

    return render_template("add_book.html")


@app.route("/edit/<int:book_id>", methods=["GET", "POST"])
def edit_book(book_id):
    with get_db() as conn:
        book = conn.execute(
            "SELECT * FROM books WHERE id=?", (book_id,)
        ).fetchone()

        if book is None:
            return "Book not found", 404

        if request.method == "POST":
            title = request.form["title"].strip()
            author = request.form["author"].strip()
            price = float(request.form["price"])
            stock = int(request.form["stock"])

            if not title or not author or price < 0 or stock < 0:
                return "Invalid book details", 400

            conn.execute("""
                UPDATE books
                SET title=?, author=?, price=?, stock=?
                WHERE id=?
            """, (title, author, price, stock, book_id))

            return redirect(url_for("index"))

    return render_template("edit_book.html", book=book)


@app.route("/delete/<int:book_id>", methods=["POST"])
def delete_book(book_id):
    with get_db() as conn:
        existing_order = conn.execute(
            "SELECT id FROM orders WHERE book_id=? LIMIT 1",
            (book_id,)
        ).fetchone()

        if existing_order:
            return "Cannot delete a book linked to an order.", 409

        conn.execute("DELETE FROM books WHERE id=?", (book_id,))

    return redirect(url_for("index"))


@app.route("/orders")
def orders():
    with get_db() as conn:
        all_orders = conn.execute("""
            SELECT orders.*, books.title
            FROM orders
            JOIN books ON orders.book_id = books.id
            ORDER BY orders.id DESC
        """).fetchall()

        books = conn.execute(
            "SELECT * FROM books WHERE stock > 0"
        ).fetchall()

    return render_template("orders.html", orders=all_orders, books=books)


@app.route("/order/add", methods=["POST"])
def add_order():
    customer = request.form["customer"].strip()
    book_id = int(request.form["book_id"])
    quantity = int(request.form["quantity"])

    if not customer or quantity <= 0:
        return "Invalid order details", 400

    with get_db() as conn:
        book = conn.execute(
            "SELECT stock FROM books WHERE id=?", (book_id,)
        ).fetchone()

        if book is None or book["stock"] < quantity:
            return "Book unavailable or insufficient stock.", 400

        conn.execute("""
            INSERT INTO orders (customer, book_id, quantity)
            VALUES (?, ?, ?)
        """, (customer, book_id, quantity))

        conn.execute(
            "UPDATE books SET stock = stock - ? WHERE id=?",
            (quantity, book_id)
        )

    return redirect(url_for("orders"))


@app.route("/order/status/<int:order_id>", methods=["POST"])
def update_order(order_id):
    status = request.form["status"]

    if status not in ("Pending", "Shipped", "Delivered", "Cancelled"):
        return "Invalid status", 400

    with get_db() as conn:
        order = conn.execute(
            "SELECT * FROM orders WHERE id=?", (order_id,)
        ).fetchone()

        if order is None:
            return "Order not found", 404

        old_status = order["status"]

        if old_status == "Cancelled" and status != "Cancelled":
            return "Cancelled orders cannot be reopened.", 400

        if status == "Cancelled" and old_status != "Cancelled":
            conn.execute(
                "UPDATE books SET stock = stock + ? WHERE id=?",
                (order["quantity"], order["book_id"])
            )

        conn.execute(
            "UPDATE orders SET status=? WHERE id=?",
            (status, order_id)
        )

    return redirect(url_for("orders"))


@app.route("/order/delete/<int:order_id>", methods=["POST"])
def delete_order(order_id):
    with get_db() as conn:
        order = conn.execute(
            "SELECT * FROM orders WHERE id=?", (order_id,)
        ).fetchone()

        if order is None:
            return "Order not found", 404

        if order["status"] != "Cancelled":
            conn.execute(
                "UPDATE books SET stock = stock + ? WHERE id=?",
                (order["quantity"], order["book_id"])
            )

        conn.execute("DELETE FROM orders WHERE id=?", (order_id,))

    return redirect(url_for("orders"))


init_db()

if __name__ == "__main__":
    app.run(debug=True)
