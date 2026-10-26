// Synthetic detector fixture; never executed as application code.
function requestSql(req: any, db: any) {
  // ruleid: nestjs-public-request-to-sql-text-local
  db.query(req.query.sql);
}
function parameterizedValue(req: any, db: any) {
  // ok: nestjs-public-request-to-sql-text-local
  db.query("SELECT * FROM items WHERE name = $1", [req.query.name]);
}
