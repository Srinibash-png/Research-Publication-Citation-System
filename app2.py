import os
from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error

load_dotenv()
app = Flask(__name__)

def get_db_connection():
    """Create a new MySQL connection using settings from the .env file."""
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "research_db"),
    )

def error_response(message, status=400):
    return jsonify({"error": message}), status

@app.route("/")
def home():
    return render_template("index.html")

@app.get("/api/health")
def health():
    """Check whether Flask can connect to MySQL."""
    try:
        conn = get_db_connection()
        conn.close()
        return jsonify({"status": "ok", "database": "connected"})
    except Error as exc:
        app.logger.exception("Database health check failed")
        return error_response("Cannot connect to MySQL. Check your .env settings and that MySQL is running.", 500)

@app.get("/api/papers")
def list_papers():
    """Return papers with author names and citation counts."""
    search = request.args.get("search", "").strip()
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        sql = """
            SELECT
                rp.paper_id, rp.title, rp.abstract, rp.publication_year,
                rp.journal_name, rp.doi,
                GROUP_CONCAT(DISTINCT a.author_name ORDER BY pa.author_order SEPARATOR ', ') AS authors,
                COUNT(DISTINCT c.citing_paper_id) AS citation_count
            FROM ResearchPapers rp
            LEFT JOIN PaperAuthors pa ON pa.paper_id = rp.paper_id
            LEFT JOIN Authors a ON a.author_id = pa.author_id
            LEFT JOIN Citations c ON c.cited_paper_id = rp.paper_id
            WHERE (%s = '' OR rp.title LIKE %s OR rp.journal_name LIKE %s
                   OR a.author_name LIKE %s OR rp.abstract LIKE %s)
            GROUP BY rp.paper_id, rp.title, rp.abstract, rp.publication_year,
                     rp.journal_name, rp.doi
            ORDER BY rp.paper_id DESC
        """
        like = f"%{search}%"
        cursor.execute(sql, (search, like, like, like, like))
        papers = cursor.fetchall()
        cursor.close()
        return jsonify(papers)
    except Error:
        app.logger.exception("Could not list papers")
        return error_response("Could not retrieve papers. Check the database setup.", 500)
    finally:
        if conn and conn.is_connected():
            conn.close()

@app.post("/api/papers")
def create_paper():
    """Create a paper and link it to one author for this starter version."""
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    author_name = (data.get("author_name") or "").strip()
    author_email = (data.get("author_email") or "").strip() or None
    affiliation = (data.get("affiliation") or "").strip() or None
    abstract = (data.get("abstract") or "").strip() or None
    journal_name = (data.get("journal_name") or "").strip() or None
    doi = (data.get("doi") or "").strip() or None
    year = data.get("publication_year")

    if not title or not author_name or not year:
        return error_response("Title, author name, and publication year are required.")
    try:
        year = int(year)
        if year < 1000 or year > 9999:
            return error_response("Enter a valid four-digit publication year.")
    except (TypeError, ValueError):
        return error_response("Publication year must be a number.")

    conn = None
    try:
        conn = get_db_connection()
        conn.start_transaction()
        cursor = conn.cursor(dictionary=True)

        # DOI is unique when provided, so report a friendly message for duplicates.
        if doi:
            cursor.execute("SELECT paper_id FROM ResearchPapers WHERE doi = %s", (doi,))
            if cursor.fetchone():
                conn.rollback()
                return error_response("A paper with this DOI already exists.", 409)

        # Reuse an author by email when supplied; otherwise match by name.
        if author_email:
            cursor.execute("SELECT author_id FROM Authors WHERE email = %s", (author_email,))
        else:
            cursor.execute(
                "SELECT author_id FROM Authors WHERE author_name = %s AND email IS NULL",
                (author_name,)
            )
        author = cursor.fetchone()

        if author:
            author_id = author["author_id"]
        else:
            cursor.execute(
                "INSERT INTO Authors (author_name, email, affiliation) VALUES (%s, %s, %s)",
                (author_name, author_email, affiliation)
            )
            author_id = cursor.lastrowid

        cursor.execute(
            """INSERT INTO ResearchPapers
               (title, abstract, publication_year, journal_name, doi)
               VALUES (%s, %s, %s, %s, %s)""",
            (title, abstract, year, journal_name, doi)
        )
        paper_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO PaperAuthors (paper_id, author_id, author_order) VALUES (%s, %s, %s)",
            (paper_id, author_id, 1)
        )
        conn.commit()
        cursor.close()
        return jsonify({"message": "Research paper added successfully.", "paper_id": paper_id}), 201
    except Error as exc:
        if conn and conn.is_connected():
            conn.rollback()
        app.logger.exception("Could not create paper")
        # Avoid returning database credentials or internal details to the browser.
        return error_response("Could not save the paper. Check required fields and database constraints.", 500)
    finally:
        if conn and conn.is_connected():
            conn.close()

@app.get("/api/papers/<int:paper_id>")
def get_paper(paper_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """SELECT rp.paper_id, rp.title, rp.abstract, rp.publication_year,
                      rp.journal_name, rp.doi,
                      GROUP_CONCAT(DISTINCT a.author_name ORDER BY pa.author_order SEPARATOR ', ') AS authors
               FROM ResearchPapers rp
               LEFT JOIN PaperAuthors pa ON pa.paper_id = rp.paper_id
               LEFT JOIN Authors a ON a.author_id = pa.author_id
               WHERE rp.paper_id = %s
               GROUP BY rp.paper_id""",
            (paper_id,)
        )
        paper = cursor.fetchone()
        cursor.close()
        if not paper:
            return error_response("Paper not found.", 404)
        return jsonify(paper)
    except Error:
        app.logger.exception("Could not retrieve paper")
        return error_response("Could not retrieve the paper.", 500)
    finally:
        if conn and conn.is_connected():
            conn.close()

@app.get("/api/authors")
def list_authors():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """SELECT a.author_id, a.author_name, a.email, a.affiliation,
                      COUNT(DISTINCT pa.paper_id) AS publication_count
               FROM Authors a
               LEFT JOIN PaperAuthors pa ON pa.author_id = a.author_id
               GROUP BY a.author_id
               ORDER BY a.author_name"""
        )
        authors = cursor.fetchall()
        cursor.close()
        return jsonify(authors)
    except Error:
        app.logger.exception("Could not list authors")
        return error_response("Could not retrieve authors.", 500)
    finally:
        if conn and conn.is_connected():
            conn.close()

@app.post("/api/authors")
def create_author():
    data = request.get_json(silent=True) or {}
    name = (data.get("author_name") or "").strip()
    email = (data.get("email") or "").strip() or None
    affiliation = (data.get("affiliation") or "").strip() or None
    if not name:
        return error_response("Author name is required.")
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO Authors (author_name, email, affiliation) VALUES (%s, %s, %s)",
            (name, email, affiliation)
        )
        author_id = cursor.lastrowid
        conn.commit()
        cursor.close()
        return jsonify({"message": "Author added successfully.", "author_id": author_id}), 201
    except Error:
        if conn and conn.is_connected():
            conn.rollback()
        app.logger.exception("Could not create author")
        return error_response("Could not add author. The email may already be registered.", 409)
    finally:
        if conn and conn.is_connected():
            conn.close()

@app.post("/api/citations")
def create_citation():
    data = request.get_json(silent=True) or {}
    try:
        citing_id = int(data.get("citing_paper_id"))
        cited_id = int(data.get("cited_paper_id"))
    except (TypeError, ValueError):
        return error_response("Select both the citing paper and the cited paper.")
    if citing_id == cited_id:
        return error_response("A paper cannot cite itself.")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO Citations (citing_paper_id, cited_paper_id) VALUES (%s, %s)",
            (citing_id, cited_id)
        )
        conn.commit()
        cursor.close()
        return jsonify({"message": "Citation recorded successfully."}), 201
    except Error as exc:
        if conn and conn.is_connected():
            conn.rollback()
        app.logger.exception("Could not create citation")
        # Covers duplicate citation and invalid paper IDs (foreign-key failure).
        return error_response("Could not record citation. Check that both papers exist and this citation is not already recorded.", 409)
    finally:
        if conn and conn.is_connected():
            conn.close()

@app.get("/api/statistics")
def statistics():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT COUNT(*) AS total_papers FROM ResearchPapers")
        total_papers = cursor.fetchone()["total_papers"]
        cursor.execute("SELECT COUNT(*) AS total_authors FROM Authors")
        total_authors = cursor.fetchone()["total_authors"]
        cursor.execute("SELECT COUNT(*) AS total_citations FROM Citations")
        total_citations = cursor.fetchone()["total_citations"]
        cursor.execute(
            """SELECT rp.paper_id, rp.title, COUNT(c.citing_paper_id) AS citation_count
               FROM ResearchPapers rp
               LEFT JOIN Citations c ON c.cited_paper_id = rp.paper_id
               GROUP BY rp.paper_id, rp.title
               ORDER BY citation_count DESC, rp.title
               LIMIT 5"""
        )
        top_papers = cursor.fetchall()
        cursor.close()
        return jsonify({
            "total_papers": total_papers,
            "total_authors": total_authors,
            "total_citations": total_citations,
            "top_papers": top_papers
        })
    except Error:
        app.logger.exception("Could not retrieve statistics")
        return error_response("Could not retrieve statistics.", 500)
    finally:
        if conn and conn.is_connected():
            conn.close()

if __name__ == "__main__":
    # Debug is useful locally. Turn it off before deploying publicly.
    app.run(debug=True)
