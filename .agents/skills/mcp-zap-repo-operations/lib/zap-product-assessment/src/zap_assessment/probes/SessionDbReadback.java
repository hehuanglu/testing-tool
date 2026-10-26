import java.sql.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.io.*;
import java.nio.file.*;
import java.nio.file.attribute.PosixFilePermissions;

/** Run-owned read-only HSQL decoder. Emits cells only to the private auditor pipe.
 * No reflection into the scanner, secret argv, arbitrary JDBC URL or network.
 */
public final class SessionDbReadback {
    private static String q(String s) {return "\""+s.replace("\\","\\\\").replace("\"","\\\"")+"\"";}
    private static void scan(Connection c) throws Exception {
        long rows=0,cells=0,bytes=0;int tables=0;
        try(var names=c.getMetaData().getTables(null,"PUBLIC","%",new String[]{"TABLE"})) {
            while(names.next()) {
                String table=names.getString("TABLE_NAME");
                if(!table.matches("[A-Z0-9_]+"))throw new IOException("unsupported table name");
                tables++;
                System.out.println("{\"kind\":\"table\",\"name\":"+q(table)+"}");
                try(var s=c.createStatement();var r=s.executeQuery("SELECT * FROM \"PUBLIC\".\""+table+"\"")) {
                    var meta=r.getMetaData();int columns=meta.getColumnCount();long rowIndex=0;
                    while(r.next()) {
                        if(++rows>100000)throw new IOException("row budget");
                        rowIndex++;
                        for(int i=1;i<=columns;i++) {
                            int type=meta.getColumnType(i);byte[] value;
                            if(type==Types.BINARY || type==Types.VARBINARY || type==Types.LONGVARBINARY || type==Types.BLOB) {
                                value=r.getBytes(i);
                            } else if(type==Types.ARRAY || type==Types.JAVA_OBJECT || type==Types.OTHER || type==Types.STRUCT || type==Types.SQLXML) {
                                throw new IOException("unsupported SQL decoder");
                            } else {
                                String text=r.getString(i);value=text==null?null:text.getBytes(StandardCharsets.UTF_8);
                            }
                            if(value==null)continue;
                            if(value.length>8*1024*1024 || (bytes+=value.length)>128*1024*1024)throw new IOException("byte budget");
                            cells++;
                            System.out.println("{\"kind\":\"cell\",\"table\":"+q(table)+",\"row\":"+rowIndex+",\"column\":"+q(meta.getColumnName(i))+",\"sqlType\":"+type+",\"base64\":"+q(Base64.getEncoder().encodeToString(value))+"}");
                        }
                    }
                }
            }
        }
        System.out.println("{\"kind\":\"complete\",\"tables\":"+tables+",\"rows\":"+rows+",\"cells\":"+cells+",\"decodedBytes\":"+bytes+"}");
    }
    private static void privateControl() throws Exception {
        // Only an in-container bridge supplies this pipe. Never host argv/env.
        String secret=new BufferedReader(new InputStreamReader(System.in,StandardCharsets.UTF_8)).readLine();
        if(secret==null || secret.length()<12 || secret.length()>8192 ||
                secret.chars().anyMatch(ch->ch<32 || ch>126))throw new IOException("private source unsupported");
        Path zone=Path.of("/tmp/w5-private-db-control");
        Files.createDirectory(zone,PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rwx------")));
        var forms=new LinkedHashMap<String,String>();
        byte[] raw=secret.getBytes(StandardCharsets.UTF_8);
        forms.put("raw-utf8",secret);
        forms.put("base64-standard",Base64.getEncoder().encodeToString(raw));
        forms.put("base64-url",Base64.getUrlEncoder().withoutPadding().encodeToString(raw));
        var percent=new StringBuilder();var escaped=new StringBuilder();
        for(byte value:raw) {percent.append(String.format("%%%02X",value&255));escaped.append(String.format("\\u%04x",value&255));}
        forms.put("url-percent",percent.toString());forms.put("json-escape",escaped.toString());
        String url="jdbc:hsqldb:file:/tmp/w5-private-db-control/session";
        try(var c=DriverManager.getConnection(url,"SA","")) {
            c.createStatement().execute("CREATE CACHED TABLE PRIVATE_SOURCE_CONTROL(ENCODING VARCHAR(32),TEXT_VALUE LONGVARCHAR,BINARY_VALUE LONGVARBINARY)");
            try(var s=c.prepareStatement("INSERT INTO PRIVATE_SOURCE_CONTROL VALUES(?,?,?)")) {
                for(var entry:forms.entrySet()) {
                    s.setString(1,entry.getKey());s.setString(2,entry.getValue());
                    s.setBytes(3,entry.getValue().getBytes(StandardCharsets.UTF_8));s.executeUpdate();
                }
            }
            c.createStatement().execute("SHUTDOWN");
        }
        // Exercise the same typed-cell reader on an actual closed file DB.
        try(var c=DriverManager.getConnection(url+";readonly=true;files_readonly=true;shutdown=true","SA","")) {scan(c);}
    }
    public static void main(String[] args) {
        try {
            Class.forName("org.hsqldb.jdbc.JDBCDriver");
            if(args.length!=1)throw new IOException("one fixed reader mode required");
            if(args[0].equals("selftest")) {
                String secret=new BufferedReader(new InputStreamReader(System.in,StandardCharsets.UTF_8)).readLine();
                if(secret==null || secret.length()<12)throw new IOException("missing private seed");
                try(var c=DriverManager.getConnection("jdbc:hsqldb:mem:w5readercontrol","SA","")) {
                    c.createStatement().execute("CREATE TABLE CANARY_CONTROL(TEXT_VALUE LONGVARCHAR,BINARY_VALUE LONGVARBINARY)");
                    try(var s=c.prepareStatement("INSERT INTO CANARY_CONTROL VALUES(?,?)")) {
                        s.setString(1,secret);s.setBytes(2,secret.getBytes(StandardCharsets.UTF_8));s.executeUpdate();
                    }
                    scan(c);
                }
            } else if(args[0].equals("private-control")) {
                privateControl();
            } else if(args[0].equals("session")) {
                try(var c=DriverManager.getConnection("jdbc:hsqldb:file:/session/w5-saved-session.session;readonly=true;files_readonly=true;shutdown=true","SA","")) {
                    scan(c);
                }
            } else throw new IOException("unsupported reader mode");
        } catch(Exception e) {
            // No JDBC/error text can escape the private decoder on failure.
            System.out.println("{\"kind\":\"blocked\",\"reason\":\"database_decode_failed\",\"errorType\":"+q(e.getClass().getName())+"}");
            System.exit(2);
        }
    }
}
