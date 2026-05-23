// CAS 密码加密 — 被 crawler.py 调用
var fs = require('fs');
var vm = require('vm');

var code = fs.readFileSync(__dirname + '/encrypt.js', 'utf-8');
vm.runInThisContext(code, 'encrypt.js');

var password = process.argv[2];
var salt = process.argv[3];

var encrypted = encryptPassword(password, salt);
console.log(encrypted);
