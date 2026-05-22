from dbctx.mysql import parse_mysql_dsn


def test_parse_go_style_mysql_dsn():
    parsed = parse_mysql_dsn("user:pass@tcp(localhost:3307)/order_db")
    assert parsed["host"] == "localhost"
    assert parsed["port"] == 3307
    assert parsed["user"] == "user"
    assert parsed["password"] == "pass"
    assert parsed["database"] == "order_db"


def test_parse_uri_mysql_dsn():
    parsed = parse_mysql_dsn("mysql://user:pass@db.example.com:3306/order_db")
    assert parsed["host"] == "db.example.com"
    assert parsed["port"] == 3306
    assert parsed["user"] == "user"
    assert parsed["password"] == "pass"
    assert parsed["database"] == "order_db"

