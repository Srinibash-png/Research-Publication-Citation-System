CREATE DATABASE IF NOT EXISTS research_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE research_db;

CREATE TABLE IF NOT EXISTS Authors (
    author_id INT PRIMARY KEY AUTO_INCREMENT,
    author_name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE,
    affiliation VARCHAR(200)
);

CREATE TABLE IF NOT EXISTS ResearchPapers (
    paper_id INT PRIMARY KEY AUTO_INCREMENT,
    title VARCHAR(255) NOT NULL,
    abstract TEXT,
    publication_year YEAR,
    journal_name VARCHAR(200),
    doi VARCHAR(255) UNIQUE
);

CREATE TABLE IF NOT EXISTS PaperAuthors (
    paper_id INT NOT NULL,
    author_id INT NOT NULL,
    author_order INT NOT NULL DEFAULT 1,
    PRIMARY KEY (paper_id, author_id),
    CONSTRAINT fk_paperauthors_paper
        FOREIGN KEY (paper_id) REFERENCES ResearchPapers(paper_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_paperauthors_author
        FOREIGN KEY (author_id) REFERENCES Authors(author_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Citations (
    citing_paper_id INT NOT NULL,
    cited_paper_id INT NOT NULL,
    PRIMARY KEY (citing_paper_id, cited_paper_id),
    CONSTRAINT fk_citations_citing
        FOREIGN KEY (citing_paper_id) REFERENCES ResearchPapers(paper_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_citations_cited
        FOREIGN KEY (cited_paper_id) REFERENCES ResearchPapers(paper_id)
        ON DELETE CASCADE,
    CONSTRAINT chk_no_self_citation
        CHECK (citing_paper_id <> cited_paper_id)
);

CREATE TABLE IF NOT EXISTS Keywords (
    keyword_id INT PRIMARY KEY AUTO_INCREMENT,
    keyword_name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS PaperKeywords (
    paper_id INT NOT NULL,
    keyword_id INT NOT NULL,
    PRIMARY KEY (paper_id, keyword_id),
    FOREIGN KEY (paper_id) REFERENCES ResearchPapers(paper_id)
        ON DELETE CASCADE,
    FOREIGN KEY (keyword_id) REFERENCES Keywords(keyword_id)
        ON DELETE CASCADE
);

-- Optional sample data: run this section only once if you want demo records.
-- INSERT INTO Authors (author_name, email, affiliation)
-- VALUES ('Rahul Sharma', 'rahul@example.com', 'Example University'),
--        ('Priya Das', 'priya@example.com', 'Example Institute');
-- INSERT INTO ResearchPapers (title, abstract, publication_year, journal_name, doi)
-- VALUES ('Machine Learning in Healthcare', 'An example abstract.', 2024, 'Example Journal', '10.1234/example.2024.001'),
--        ('Deep Learning for Medical Diagnosis', 'Another example abstract.', 2025, 'Example Journal', '10.1234/example.2025.001');
-- INSERT INTO PaperAuthors (paper_id, author_id, author_order) VALUES (1, 1, 1), (2, 2, 1);
-- INSERT INTO Citations (citing_paper_id, cited_paper_id) VALUES (2, 1);
