"""Question bank for the software-engineer internship test: basic questions across frontend, backend, database, AI and Git.
Each row: (topic, question, RIGHT answer, wrong 1, wrong 2, wrong 3). Letters are shuffled when seeded, so 'a' is not always right.
Every test draws 30 questions at random, balanced by QUOTAS. The bank has ~2.5x more questions than a test uses, so retries differ.
Add more any time with `flask seed-mcq` after editing this file (existing questions are never duplicated)."""
import random

QUOTAS = {  # 30 per test
    "html": 2, "css": 2, "javascript": 3, "react": 1,                      # frontend (8)
    "python": 3, "java": 2, "nodejs": 2, "http_api": 2,                    # backend (9)
    "sql": 4, "nosql_db": 2,                                               # database (6)
    "ai": 5,                                                               # AI / ML (5)
    "git": 2,                                                              # Git / GitHub (2)
}
GROUPS = {"Frontend": ("html", "css", "javascript", "react"), "Backend": ("python", "java", "nodejs", "http_api"),
          "Database": ("sql", "nosql_db"), "AI": ("ai",), "Git": ("git",)}

BANK = [
    # ---------------------------------------------------------------- HTML
    ("html", "Which HTML tag creates the largest heading?", "<h1>", "<head>", "<h6>", "<heading>"),
    ("html", "Which attribute gives alternative text for an image?", "alt", "title", "src", "href"),
    ("html", "Which tag creates a hyperlink?", "<a>", "<link>", "<url>", "<href>"),
    ("html", "Which semantic tag is meant for a group of navigation links?", "<nav>", "<div>", "<span>", "<list>"),
    ("html", "Which input type hides the characters the user types?", "password", "hidden", "secret", "text"),
    # ---------------------------------------------------------------- CSS
    ("css", "Which CSS property changes the colour of text?", "color", "font-color", "text-color", "foreground"),
    ("css", "Which property adds space OUTSIDE an element's border?", "margin", "padding", "spacing", "outline"),
    ("css", "Which display value makes children lay out in a flexible row or column?", "flex", "block", "inline", "static"),
    ("css", "Which selector targets the element with id=\"main\"?", "#main", ".main", "*main", "@main"),
    ("css", "What does position: absolute do?", "Places the element relative to its nearest positioned ancestor", "Keeps it in the normal flow", "Always fixes it to the browser window", "Centres it horizontally"),
    # ---------------------------------------------------------------- JavaScript / TypeScript
    ("javascript", "Which keyword declares a block-scoped variable that can be reassigned?", "let", "const", "var", "define"),
    ("javascript", "What does typeof \"hello\" return?", "\"string\"", "\"text\"", "\"char\"", "\"word\""),
    ("javascript", "Which array method adds an item to the END of an array?", "push()", "pop()", "shift()", "unshift()"),
    ("javascript", "What does the === operator check?", "Both value and type are equal", "Only the value", "Only the type", "It assigns a value"),
    ("javascript", "Which method turns a JSON string into a JavaScript object?", "JSON.parse()", "JSON.stringify()", "JSON.object()", "JSON.toObject()"),
    ("javascript", "What does typeof NaN return?", "\"number\"", "\"NaN\"", "\"undefined\"", "\"string\""),
    ("javascript", "Which array method returns a NEW array with every element transformed?", "map()", "forEach()", "push()", "splice()"),
    ("javascript", "What is async/await used for?", "Writing asynchronous (promise-based) code in a readable way", "Running code on several CPU cores", "Styling elements", "Connecting to a database only"),
    ("javascript", "TypeScript is best described as:", "A superset of JavaScript that adds static types", "A database language", "A CSS framework", "A replacement for HTML"),
    # ---------------------------------------------------------------- React
    ("react", "What is JSX?", "A syntax that lets you write HTML-like markup inside JavaScript", "A database query language", "A CSS preprocessor", "A Node.js package manager"),
    ("react", "Which hook stores state in a function component?", "useState", "useDom", "useClass", "useRender"),
    ("react", "How does a parent component pass data to a child component?", "Through props", "Through cookies", "Through selectors", "Through middleware"),
    ("react", "Why does React ask for a key on list items?", "To identify which items changed, were added or removed", "To style the items", "To encrypt the items", "To sort the items"),
    # ---------------------------------------------------------------- Python
    ("python", "Which of these is a Python list?", "[1, 2, 3]", "(1, 2, 3)", "{1, 2, 3}", "<1, 2, 3>"),
    ("python", "Which keyword defines a function in Python?", "def", "function", "fun", "define"),
    ("python", "What does len(\"abc\") return?", "3", "2", "4", "\"abc\""),
    ("python", "Which of these data types is immutable?", "tuple", "list", "dict", "set"),
    ("python", "How does a single-line comment start in Python?", "#", "//", "/*", "--"),
    ("python", "What is pip used for?", "Installing Python packages", "Compiling Python to C", "Formatting code", "Running a web server"),
    ("python", "What does print(2 ** 3) output?", "8", "6", "5", "23"),
    # ---------------------------------------------------------------- Java
    ("java", "Which keyword creates a new object in Java?", "new", "create", "make", "object"),
    ("java", "What is the entry point of a Java program?", "public static void main(String[] args)", "void start()", "public void run()", "static int begin()"),
    ("java", "Java source code is compiled into:", "Bytecode that runs on the JVM", "Machine code only for Windows", "HTML", "SQL scripts"),
    ("java", "Which of these is NOT a primitive type in Java?", "String", "int", "boolean", "char"),
    ("java", "Which keyword is used to inherit from another class?", "extends", "inherits", "derives", "imports"),
    ("java", "What does a static method belong to?", "The class itself, so it can be called without creating an object", "Only one particular object", "The database", "The operating system"),
    # ---------------------------------------------------------------- Node.js
    ("nodejs", "What is Node.js?", "A JavaScript runtime that runs outside the browser", "A CSS framework", "A relational database", "A web browser"),
    ("nodejs", "Which command installs a package from npm?", "npm install", "node get", "npm compile", "nodejs add"),
    ("nodejs", "Which file lists a Node project's dependencies?", "package.json", "index.html", "node.config", "server.xml"),
    ("nodejs", "Express is:", "A web framework for Node.js", "A database", "A testing browser", "A CSS preprocessor"),
    ("nodejs", "In CommonJS, which function loads a module?", "require()", "include()", "load()", "fetchModule()"),
    # ---------------------------------------------------------------- HTTP / REST / security basics
    ("http_api", "Which HTTP method is normally used to READ data?", "GET", "POST", "DELETE", "PUT"),
    ("http_api", "What does HTTP status 404 mean?", "Not Found", "Server error", "OK", "Unauthorized"),
    ("http_api", "Which HTTP status code means the request succeeded?", "200", "301", "404", "500"),
    ("http_api", "Which format do REST APIs most commonly use to exchange data?", "JSON", "PNG", "MP3", "EXE"),
    ("http_api", "What does CORS control?", "Which web origins may call an API from a browser", "How passwords are hashed", "How database indexes work", "How images are compressed"),
    ("http_api", "How should a server store user passwords?", "As a salted hash (for example bcrypt)", "As plain text", "As base64 text", "Same as the username"),
    # ---------------------------------------------------------------- SQL
    ("sql", "Which SQL statement reads data from a table?", "SELECT", "GET", "FETCH", "OPEN"),
    ("sql", "Which clause filters rows before grouping?", "WHERE", "ORDER BY", "LIMIT", "JOIN"),
    ("sql", "What does a PRIMARY KEY do?", "Uniquely identifies each row in a table", "Encrypts the table", "Sorts the table", "Copies the table"),
    ("sql", "Which function counts rows?", "COUNT(*)", "SUM(*)", "TOTAL()", "NUMBER()"),
    ("sql", "What does a JOIN do?", "Combines rows from two tables using a related column", "Deletes duplicate rows", "Creates a backup", "Renames a column"),
    ("sql", "Which clause sorts the result?", "ORDER BY", "SORT BY", "GROUP BY", "ARRANGE"),
    ("sql", "Which statement adds a new row to a table?", "INSERT INTO", "ADD ROW", "PUT", "APPEND"),
    ("sql", "What is a FOREIGN KEY?", "A column that refers to the primary key of another table", "A column that must always be empty", "A password column", "A column that is hidden"),
    ("sql", "GROUP BY is usually combined with:", "Aggregate functions such as COUNT or SUM", "Only the DROP statement", "Only images", "Only comments"),
    # ---------------------------------------------------------------- NoSQL and database concepts
    ("nosql_db", "MongoDB stores data as:", "JSON-like documents", "Rows in fixed tables only", "Spreadsheets", "Plain text files"),
    ("nosql_db", "Which of these is a NoSQL database?", "MongoDB", "MySQL", "PostgreSQL", "SQLite"),
    ("nosql_db", "Redis is most often used as:", "An in-memory key-value store or cache", "A word processor", "A CSS library", "A version control tool"),
    ("nosql_db", "What is a database index for?", "Making lookups faster (at the cost of extra storage and slower writes)", "Encrypting data", "Deleting old rows", "Drawing charts"),
    ("nosql_db", "In ACID, what does the letter A stand for?", "Atomicity", "Availability", "Accuracy", "Automation"),
    # ---------------------------------------------------------------- AI / ML
    ("ai", "What does AI stand for?", "Artificial Intelligence", "Automated Internet", "Applied Interface", "Advanced Input"),
    ("ai", "Machine learning means:", "Computers learn patterns from data instead of following only fixed rules", "Machines repairing themselves", "Writing HTML faster", "Storing data in tables"),
    ("ai", "Supervised learning is trained on:", "Labelled examples (inputs with the correct answers)", "Only unlabelled data", "No data at all", "Only images"),
    ("ai", "Which Python library is widely used for classical machine learning?", "scikit-learn", "Bootstrap", "jQuery", "Laravel"),
    ("ai", "Overfitting means a model:", "Does very well on training data but poorly on new data", "Is too small to train", "Cannot be saved", "Uses too little memory"),
    ("ai", "Neural networks are loosely inspired by:", "Connected neurons in the brain", "Spreadsheets", "Relational tables", "Web servers"),
    ("ai", "NLP stands for:", "Natural Language Processing", "New Logic Programming", "Network Layer Protocol", "Numeric Linear Programming"),
    ("ai", "What is a training set?", "Data used to teach a model", "A list of bugs", "A set of passwords", "A folder of screenshots"),
    ("ai", "Predicting the price of a house is what kind of task?", "Regression", "Classification", "Translation", "Compression"),
    ("ai", "What does LLM stand for?", "Large Language Model", "Low Level Machine", "Linear Logic Method", "Linked List Manager"),
    ("ai", "In generative AI, a prompt is:", "The input or instruction given to the model", "The model's weights", "A type of GPU", "An error message"),
    ("ai", "Which of these is a deep learning framework?", "PyTorch", "Pandas", "Matplotlib", "Flask"),
    ("ai", "A 'hallucination' in an AI model means:", "A confident answer that is wrong or made up", "A crash of the server", "A very slow reply", "An answer in another language"),
    # ---------------------------------------------------------------- Git / GitHub
    ("git", "Which command copies a remote repository to your computer?", "git clone", "git copy", "git fetch-all", "git download"),
    ("git", "Which command stages changes for the next commit?", "git add", "git save", "git push", "git commit"),
    ("git", "Which command records your staged changes in history?", "git commit", "git store", "git record", "git stage-all"),
    ("git", "Which command uploads your local commits to GitHub?", "git push", "git upload", "git send", "git export"),
    ("git", "What is the difference between Git and GitHub?", "Git is the version-control tool; GitHub is a website that hosts repositories", "They are the same thing", "Git is a website; GitHub is a command", "GitHub is a programming language"),
    ("git", "What is a .gitignore file for?", "Listing files that Git should not track", "Deleting the repository", "Storing passwords", "Speeding up the internet"),
]


def rows_for_insert():
    """(topic, question, a, b, c, d, correct_letter). The right answer cycles through a, b, c, d so every letter is right equally often."""
    out = []
    for i, (topic, q, right, *wrong) in enumerate(BANK):
        random.Random(i).shuffle(wrong)
        pos = i % 4
        opts = wrong[:pos] + [right] + wrong[pos:]
        out.append((topic, q, *opts, "abcd"[pos]))
    return out


def seed():
    """Insert any question that is not in the database yet. Returns how many were added."""
    import db
    n = 0
    for r in rows_for_insert():
        n += db.run("""insert into mcq_questions (topic, question, option_a, option_b, option_c, option_d, correct)
                       values (%s,%s,%s,%s,%s,%s,%s) on conflict (question) do nothing""", r)
    return n
