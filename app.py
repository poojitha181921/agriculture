from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from datetime import datetime, date
import uuid, random, numpy as np
from sklearn.linear_model import LinearRegression

# --- CONFIG ---
app = Flask(__name__)

# Replace with your own MySQL details
app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://fap_user:your_password@localhost/fap_presale"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# --- MODELS ---
class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.String(36), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    zone = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    orders = relationship("Order", back_populates="product")

class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.String(36), primary_key=True)
    product_id = db.Column(db.String(36), db.ForeignKey("products.id"))
    customer = db.Column(db.String(100), nullable=False)
    qty = db.Column(db.Float, nullable=False)
    zone = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50), default="Booked")
    placed_at = db.Column(db.DateTime, default=datetime.utcnow)
    product = relationship("Product", back_populates="orders")

class DailySale(db.Model):
    __tablename__ = "daily_sales"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    product_id = db.Column(db.String(36), nullable=False)
    date_iso = db.Column(db.String(20), nullable=False)
    qty = db.Column(db.Float, nullable=False)

# --- API ROUTES ---
@app.route("/products", methods=["GET", "POST"])
def manage_products():
    if request.method == "POST":
        data = request.json
        new_product = Product(
            id=str(uuid.uuid4()),
            name=data["name"],
            price=data["price"],
            zone=data["zone"]
        )
        db.session.add(new_product)
        db.session.commit()
        return jsonify({"message": "Product added", "id": new_product.id}), 201
    
    products = Product.query.all()
    return jsonify([{"id": p.id, "name": p.name, "price": p.price, "zone": p.zone} for p in products])

@app.route("/orders", methods=["POST"])
def create_order():
    data = request.json
    product = Product.query.get(data["product_id"])
    if not product:
        return jsonify({"error": "Product not found"}), 404

    new_order = Order(
        id=str(uuid.uuid4()),
        product_id=product.id,
        customer=data["customer"],
        qty=data["qty"],
        zone=product.zone
    )
    db.session.add(new_order)
    db.session.commit()
    return jsonify({"message": "Order created", "order_id": new_order.id}), 201

@app.route("/forecast/<product_id>", methods=["GET"])
def forecast_demand(product_id):
    sales = DailySale.query.filter_by(product_id=product_id).order_by(DailySale.id.desc()).limit(7).all()
    if not sales:
        return jsonify({"error": "No sales data"}), 404

    sales = list(reversed(sales))
    y = np.array([s.qty for s in sales])
    X = np.arange(len(y)).reshape(-1, 1)

    if len(y) == 1:
        pred = float(y[0])
    else:
        model = LinearRegression()
        model.fit(X, y)
        pred = model.predict([[len(y)]])[0]

    return jsonify({"predicted_demand": round(float(pred), 2)})

@app.route("/orders/<order_id>/status", methods=["PUT"])
def update_order_status(order_id):
    order = Order.query.get(order_id)
    if not order:
        return jsonify({"error": "Order not found"}), 404

    statuses = ["Booked", "Packed", "In Transit", "Out for Delivery", "Delivered"]
    try:
        current_idx = statuses.index(order.status)
        if current_idx + 1 < len(statuses):
            order.status = statuses[current_idx + 1]
    except ValueError:
        order.status = "Booked"

    db.session.commit()
    return jsonify({"order_id": order.id, "new_status": order.status})

# --- MAIN ---
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
