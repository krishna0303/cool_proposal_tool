from flask import Flask, render_template, request, redirect, url_for, jsonify
import uuid
import razorpay
import sqlite3
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv



app = Flask(__name__)
load_dotenv()
# Access Razorpay keys safely
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

# Check if keys are loaded (optional debug)
if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
    raise Exception("Razorpay keys are missing! Please check your .env file.")

# Initialize Razorpay client
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))


# 🔹 DB Setup
DB_NAME = 'proposals.db'

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def escape_special_characters(message):
    """
    Manually escape special characters for safe JavaScript rendering.
    """
    # Replace single quotes, double quotes, and other special characters
    message = message.replace("'", "&#39;")
    message = message.replace('"', "&quot;")
    message = message.replace("<", "&lt;")
    message = message.replace(">", "&gt;")
    message = message.replace("&", "&amp;")
    # Optionally handle newlines (you can adjust this if needed)
    message = message.replace("\n", "<br>")
    
    # Optionally, handle emoji characters (just keep them as they are, they won't break JavaScript)
    return message
# 🔹 Home Page → Form
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        your_name = request.form['your_name']
        crush_name = request.form['crush_name']
        message = request.form['message']
        theme = request.form['theme']
        url_id = str(uuid.uuid4())[:8]
        created_at = datetime.now()

        conn = get_db_connection()
        conn.execute('''
            INSERT INTO proposals (url_id, your_name, crush_name, message, theme, created_at, paid)
            VALUES (?, ?, ?, ?, ?, ?, 0)
        ''', (url_id, your_name, crush_name, message, theme, created_at))
        conn.commit()
        conn.close()

        return redirect(url_for('proposal', url_id=url_id))
    return render_template("index.html")


# 🔹 Preview Page → Before Payment
@app.route('/preview/<url_id>')
def preview(url_id):
    conn = get_db_connection()
    proposal = conn.execute('SELECT * FROM proposals WHERE url_id = ?', (url_id,)).fetchone()
    conn.close()

    if not proposal:
        return redirect(url_for('expired'))

    if is_expired(proposal['created_at']):
        return redirect(url_for('expired'))

    # Create Razorpay order only if not already paid
    order = razorpay_client.order.create({
        "amount": 100,  # ₹10 in paise
        "currency": "INR",
        "payment_capture": 1
    })

    paid = request.args.get("paid") == "1"

    return render_template('preview.html', proposal=proposal, order=order, key_id=RAZORPAY_KEY_ID, paid=paid)





# 🔹 Payment Success
@app.route('/payment_success', methods=['POST'])
def payment_success():
    url_id = request.form.get('url_id')

    conn = get_db_connection()
    conn.execute("UPDATE proposals SET paid = 1 WHERE url_id = ?", (url_id,))
    conn.commit()
    conn.close()

    return redirect(url_for('thank_you', url_id=url_id))


# 🔹 Thank You Page
@app.route('/thankyou/<url_id>')
def thank_you(url_id):
    return render_template("thankyou.html", url_id=url_id)


# 🔹 Final Proposal Page
@app.route('/proposal/<url_id>')
def proposal(url_id):
    with get_db_connection() as conn:
        proposal = conn.execute(
            'SELECT * FROM proposals WHERE url_id = ?', (url_id,)
        ).fetchone()

    if not proposal:
        return redirect(url_for('expired'))

    created_at_str = proposal['created_at']
    created_at_dt = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S.%f")
    if datetime.utcnow() - created_at_dt > timedelta(hours=24):
        return render_template("expired.html", unique_id=unique_id)

   # if not proposal['paid']:
    #    return redirect(url_for('preview', url_id=url_id))

    escaped_message = escape_special_characters(proposal["message"])
    return render_template("proposal.html", proposal=proposal,escaped_message=escaped_message)

# 🔹 Final Friend Roast Page
@app.route('/friend_roast/<url_id>')
def friend_roast(url_id):
    with get_db_connection() as conn:
        proposal = conn.execute(
            'SELECT * FROM proposals WHERE url_id = ?', (url_id,)
        ).fetchone()

    if not proposal:
        return redirect(url_for('expired'))

    created_at_str = proposal['created_at']
    created_at_dt = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S.%f")
    if datetime.utcnow() - created_at_dt > timedelta(hours=24):
        return render_template("expired.html", unique_id=url_id)

    if not proposal['paid']:
        return redirect(url_for('preview', url_id=url_id))

    return render_template("friend_roast.html", roast=proposal)


# 🔹 Expired Link Page
@app.route('/expired')
def expired():
    return render_template('expired.html')


# 🔹 Helper to check expiry
def is_expired(created_at_str):
    try:
        created_time = datetime.strptime(created_at_str, '%Y-%m-%d %H:%M:%S.%f')
    except:
        created_time = datetime.strptime(created_at_str, '%Y-%m-%d %H:%M:%S')

    return datetime.now() > created_time + timedelta(hours=24)


@app.route('/verify_payment', methods=['POST'])
def verify_payment():
    data = request.get_json()

    try:
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': data['razorpay_order_id'],
            'razorpay_payment_id': data['razorpay_payment_id'],
            'razorpay_signature': data['razorpay_signature']
        })

        # Payment verified, update DB
        conn = get_db_connection()
        conn.execute(
            'UPDATE proposals SET paid = 1 WHERE url_id = ?',
            (data['url_id'],)
        )
        conn.commit()
        conn.close()

        return jsonify({'status': 'success', 'url_id': data['url_id']})

    except razorpay.errors.SignatureVerificationError:
        return jsonify({'status': 'failure'})


if __name__ == "__main__":
    app.run(debug=True)
