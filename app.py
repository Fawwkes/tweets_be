import random
import psycopg2
from flask import Flask, render_template, request

app = Flask(__name__)

app.config['DATABASE'] = {
    'dbname': 'tweets',
    'user': 'postgres',
    'password': 'postgre',
    'host': 'localhost',
    'port': '5432'
}


def get_db():
    conn = psycopg2.connect(
        dbname=app.config['DATABASE']['dbname'],
        user=app.config['DATABASE']['user'],
        password=app.config['DATABASE']['password'],
        host=app.config['DATABASE']['host'],
        port=app.config['DATABASE']['port']
    )
    return conn


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        liked_tweets = request.form.getlist('liked_tweet')
        disliked_tweets = request.form.getlist('disliked_tweet')

        # Update the weights based on liked tweets
        for tweet_id in liked_tweets:
            update_weight(tweet_id, 1)

        # Update the weights based on disliked tweets
        for tweet_id in disliked_tweets:
            update_weight(tweet_id, -1)

    weights = compute_weights()  # Compute the weights

    next_tweets = get_next_tweets()

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, text, candidate FROM clustered_tweets WHERE id IN %s", (tuple(next_tweets),))
    tweets = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('index.html', tweets=tweets, weights=weights)


def update_weight(tweet_id, weight_change):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT candidate, weight FROM weights WHERE candidate = (SELECT candidate FROM clustered_tweets WHERE id = %s)", (tweet_id,))
    result = cursor.fetchone()

    if result:
        candidate, weight = result
        if weight_change > 0:
            weight += weight_change
        elif weight_change < 0 < weight:
            weight += weight_change  # You can adjust the scaling factor here if desired
        cursor.execute("UPDATE weights SET weight = %s WHERE candidate = %s", (weight, candidate))
    else:
        candidate = get_candidate(tweet_id)
        if candidate and weight_change > 0:
            cursor.execute("INSERT INTO weights (candidate, weight) VALUES (%s, %s)", (candidate, weight_change))

    conn.commit()
    cursor.close()
    conn.close()


def get_candidate(tweet_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT candidate FROM clustered_tweets WHERE id = %s", (tweet_id,))
    candidate = cursor.fetchone()
    cursor.close()
    conn.close()
    return candidate[0] if candidate else None


def get_next_tweets():
    weights = compute_weights()  # Compute the weights
    next_tweets = []
    conn = get_db()
    cursor = conn.cursor()
    for _ in range(5):
        if not weights or sum(weights.values()) == 0:
            cursor.execute("SELECT id FROM clustered_tweets ORDER BY RANDOM() LIMIT 1")
            tweet_id = cursor.fetchone()[0]
            next_tweets.append(tweet_id)
        else:
            candidates = [candidate for candidate, weight in weights.items() if weight > 0]
            candidate_probabilities = [weight for weight in weights.values() if weight > 0]
            chosen_candidate = random.choices(candidates, candidate_probabilities)[0]
            cursor.execute(
                "SELECT id FROM clustered_tweets WHERE candidate = %s ORDER BY RANDOM() LIMIT 1",
                (chosen_candidate,),
            )
            tweet_id = cursor.fetchone()[0]
            next_tweets.append(tweet_id)
    cursor.close()
    conn.close()

    return next_tweets


def compute_weights():
    weights = {}
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT candidate, weight FROM weights")
    result = cursor.fetchall()
    cursor.close()
    conn.close()

    weights.update({candidate: weight for candidate, weight in result})

    total_count = sum(weights.values())

    if total_count == 0:
        probabilities = {candidate: 1 / len(weights) for candidate in weights.keys()}
    else:
        probabilities = {candidate: count / total_count for candidate, count in weights.items()}

    return probabilities


@app.route('/reset_weights', methods=['POST'])
def reset_weights():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM weights")
    conn.commit()
    cursor.close()
    conn.close()
    return "Weights reset successfully"


if __name__ == '__main__':
    app.run()
