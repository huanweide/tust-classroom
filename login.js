var LOGIN_USERNAME_ID = ".form > .m-account > * > #username";
var LOGIN_PASSWORD_ID = ".form > .m-account > * > #password";
var LOGIN_CAPTCHA_ID = ".form > .m-account > * > #captcha";
var LOGIN_ACCOUNT_ID = ".form > .m-phone > * > #username";
var LOGIN_DYNAMIC_ID = ".form > .m-phone > * > #dynamicCode";
var LOGIN_DYNAMIC_CAPTCHA_ID = ".form > .m-phone > * > #captcha";
var LOGIN_SUBMIT_ID = "#login_submit";
var LOGIN_SUBMIT_BACKGROUND_COLOR = "";
var QR_LOGIN_ENABLED = 0;
var DEFAULT_SALT = "rjBFAaHsNkKAhpoi";
var excludeRegular = window.excludeRegular === undefined ? "用户名包含特殊字符！" : excludeRegular;
var reg = window.reg === undefined ? "" : reg;
String.prototype.trim = function () {
  return this.replace(/(^\s*)|(\s*$)/g, ""); //正则匹配空格  
}
$(function() {
    var url = location.href;
    if (url.indexOf('dynamicLogin') != -1) {
        $("#pwdLoginSpan").removeClass('selected');
        $("#phoneLoginSpan").addClass('selected');
    }
    if (url.indexOf('fidoLogin') != -1) {
        $("#pwdLoginSpan").removeClass('selected');
        $("#fidoLoginSpan").addClass('selected');
    }
    $("#captchaImg").mouseover(function () {
        $(".mask-inner").show();
    }).mouseout(function() {
        $(".mask-inner").hide();
    })

    $(".btn_quxiao").click(function() {
        $(".dz_zzc").hide();
    })

    var swiper = new Swiper('.swiper-container', {
      autoplay: 5000,	//轮播时间
      autoplayDisableOnInteraction: false, // 手动切换之后继续自动轮播
      speed: 5, // 切换速度(1切换 2平移)
      loop: true,
    })

    if (service && service != "") {
        utils.setUrlParam("pwdFromId", "?service", encodeURIComponent(service));
        utils.setUrlParam("phoneFromId", "?service", encodeURIComponent(service));
        utils.setUrlParam("loginFromId", "?service", encodeURIComponent(service));
        utils.setUrlParam("commonLoginA", "&service", encodeURIComponent(service));
        utils.setUrlParam("outUserLogin", "&service", encodeURIComponent(service));
        utils.setUrlParam("qrCodeA", "&service", encodeURIComponent(service));
        utils.setUrlParam("retrievePassId", "?service", encodeURIComponent(service));
        utils.setUrlParam("activationAccountId", "?service", encodeURIComponent(service));
        utils.setUrlParam("activationAccountIdBtn", "?service", encodeURIComponent(service));
        utils.setUrlParam("dynamicLogin_a", "&service", encodeURIComponent(service));
        utils.setUrlParam("fidoLogin_a", "&service", encodeURIComponent(service));
        utils.setUrlParam("userNameLogin_a", "&service", encodeURIComponent(service));
        utils.setUrlParam("combinedLogin_a_weiBo", "&success", encodeURIComponent(service));
        utils.setUrlParam("combinedLogin_a_weiXin", "&success", encodeURIComponent(service));
        utils.setUrlParam("combinedLogin_a_qq", "&success", encodeURIComponent(service));
        $("#iframe").attr("src", $("#iframe").attr("src")+"&success="+encodeURIComponent(service));
        setUrlForSuccessByClass(service)
    }
    var b = window.localStorage.getItem("anonbiometricso");
    var a = window.localStorage.getItem("anonbiometricsu");
    showTabHeadAndDiv(b, a);
    if ($(LOGIN_USERNAME_ID).val() != "") {
        $(LOGIN_PASSWORD_ID).focus()
    } else {
        $(LOGIN_USERNAME_ID).focus()
    }
    $(LOGIN_USERNAME_ID).focusout(function (c) {
        checkSpecificKey($(LOGIN_USERNAME_ID).val());
        checkNeedCaptcha()
    });
    $(".device-switch").click(function () {
        var c = $(this).attr("flag");
        if (c == "0") {
            $(this).find("img").attr("src", "./static/web/images/pc.png");
            $(this).attr("flag", "1");
            $(".login-pc").addClass("hide");
            $(".login-qrcode").removeClass("hide")
        } else {
            $(this).find("img").attr("src", "./static/web/images/qcode.png");
            $(this).attr("flag", "0");
            $(".login-pc").removeClass("hide");
            $(".login-qrcode").addClass("hide")
        }
    });
    $(".input_eye").click(function () {
        var c = $("#password");
        if ($(this).hasClass("eyehide")) {
            $(this).removeClass("eyehide").addClass("eyeshow");
            c.prop("type", "text")
        } else {
            $(this).removeClass("eyeshow").addClass("eyehide");
            c.prop("type", "password")
        }
    });
    $("body").on("keyup", function (c) {
        if (c.keyCode == 13) {
            startLogin($(LOGIN_SUBMIT_ID))
        }
    });
    $(LOGIN_SUBMIT_ID).click(function () {
        startLogin(this)
    });
    $(".get-code").click(function () {
        if (utils.requireInput($(LOGIN_ACCOUNT_ID), 0, 100, $("#showErrorTip"), inputMobileTip, $(LOGIN_ACCOUNT_ID).parent())) {
            return
        }
        if (captchaSwitch == "2") {
            createSliderCaptcha()
        } else {
            getDynamicCode()
        }
    });
    utils.showMsg($("#showErrorTip"), $("#showErrorTip").text())

    // 添加提示 跟随用户名密码错误一起展示
    var showErrorText = $("#showErrorTip").text();

    if (!utils.isEmptyStr(showErrorText)) {
      if (showErrorText === '您提供的用户名或者密码有误'){
        var addTip = document.createElement("div");
        addTip.innerText = "密码忘记，可以去企业微信的个人服务里重置";
        addTip.style.color = "#fff";
		addTip.style.fontSize = "12px";
        $("#showErrorTip").append(addTip)
      }
    }


    // 兼容ie8
  if (!window.atob && navigator.userAgent.indexOf('MSIE 8.0') !== -1){
    $(".cus-headers img").css({
      float: "left"
    })
    $(".cus-headers p").css({
      float: "left",
      lineHeight: "80px"
    })

    $(".wrap").css({
      top: "100px",
      background: '#787878'
    })

    $(".tabHead").css({
      float: "left",
      width: "322px",
      marginTop: "32px"
    })

    $(".login-pc").css({
      float: "left",
      width: "322px",
      paddingLeft: "12px",
      boxSizing: "border-box"
    })

    $(".help a").css({
      float: "left",
      marginRight: "8px"
    })

    $(".form .item").css({
      maxHeight: "none"
    })

    $(".tip-title img").css({
      float: "left"
    })

    $(".tip-item img").css({
      float: "left"
    })
  }
})


function startLogin(a) {
    utils.disabledBtn(a, true);
    utils.cleanRequire($(".loginFromClass"), $("#showErrorTip"));
    if (checkForm()) {
        var b = $("#cllt").val();
        if (needCaptcha && captchaSwitch == "2" && b == "userNameLogin") {
            createSliderCaptcha();
            utils.disabledBtn(a, false)
        } else {
            $(".loginFromClass").submit()
        }
    } else {
        utils.disabledBtn(a, false)
    }
}

function fidoEnabled() {
    try {
        if (_fidoEnabled == undefined || _fidoEnabled == "true") {
            return true
        }
    } catch (a) {
        console.log("捕获到异常：", a)
    }
    return false
}

function credentialsCount() {
    try {
        if (_badCredentialsCount && _badCredentialsCount == 0) {
            return true
        }
    } catch (a) {
        console.log("捕获到异常：", a)
    }
    return false
}

function showCaptchaOnLoad() {
    if (credentialsCount()) {
        reloadCaptcha(true)
    }
}

function showTabHeadAndDiv(b, a) {
    $(".login-pc").show();
    $(".login-qrcode").hide();
    if (b != "true" || !b || !a || !fidoEnabled() || !isDeviceBinded()) {
        if (type == "fidoLogin") {
            window.location.href = contextPath;
            return
        }
        $("#fidoLoginSpan").remove()
    }
    if (is_dynamicLogin != "true" || !is_dynamicLogin) {
        if (type == "dynamicLogin") {
            window.location.href = contextPath;
            return
        }
        $("#phoneLoginSpan").remove()
    }
    if (window.is_userNameLogin != undefined && window.is_userNameLogin != "true") {
        $("#pwdLoginSpan").remove()
    }
    if (isQrLoginEnabled === "true") {
        if (isQrLogin != "true" || !isQrLogin) {
            if (type == "qrLogin") {
                window.location.href = contextPath;
                return
            }
            $("#qrLoginSpan").remove()
        } else {
            $("#qrCodeA").hide()
        }
    } else {
        $("#qrLoginSpan").remove();
        $("#qrCodeA").hide()
    }
    setTimeout(function () {
        $(".tabHead").show();
        var c = $(".tabHead").width();
        var d = c * (100 / ($(".tabHead").children("span").length)) / 100;
        $(".tabHead span").css("width", d)
    }, 100);
    if ((type == "" || !type) && (cllt == "" || !cllt) && b == "true" && a != "" && a && fidoEnabled() && isDeviceBinded()) {
        $("#fidoLogin_a").addClass("loginFont_a_light");
        $("#fidoLoginDiv").show();
        $("#pwdLoginDiv").remove();
        $("#phoneLoginDiv").remove()
    } else {
        if ((type == "fidoLogin" || cllt == "fidoLogin") && fidoEnabled() && isDeviceBinded()) {
            $("#fidoLoginSpan").addClass("selected_underline");
            $("#fidoLoginDiv").show();
            $("#pwdLoginDiv").remove();
            $("#phoneLoginDiv").remove()
        } else {
            if (type == "qrLogin" || cllt == "qrLogin") {
                showQrLogin()
            } else {
                if (type == "dynamicLogin" || cllt == "dynamicLogin") {
                    $("#phoneLoginSpan").addClass("selected_underline");
                    $("#phoneLoginDiv").show();
                    $("#pwdLoginDiv").remove();
                    $("#fidoLoginDiv").remove();
                    reloadCaptcha(true)
                } else {
                    if (window.is_userNameLogin != undefined && window.is_userNameLogin != "true") {
                        if (isQrLoginEnabled === "true" && (is_dynamicLogin != "true" || !is_dynamicLogin)) {
                            showQrLogin();
                            return
                        }
                        $("#phoneLoginSpan").addClass("selected_underline");
                        $("#phoneLoginDiv").show();
                        $("#pwdLoginDiv").remove();
                        $("#fidoLoginDiv").remove();
                        reloadCaptcha(true)
                    } else {
                        $("#pwdLoginSpan").addClass("selected_underline");
                        $("#pwdLoginDiv").show();
                        $("#phoneLoginDiv").remove();
                        $("#fidoLoginDiv").remove();
                        checkNeedCaptcha();
                        showCaptchaOnLoad()
                    }
                }
            }
        }
    }
    reloadInput()
}

function showQrLogin() {
    QR_LOGIN_ENABLED = 1;
    $(".tabHead").find("span").removeClass("selected_underline");
    $("#qrLoginSpan").addClass("selected_underline");
    $(".login-pc").hide();
    $(".login-qrcode").show();
    getQrCode();
    window.history.replaceState(null, null, "?type=qrLogin")
}

function disableLoginBtn() {
    LOGIN_SUBMIT_BACKGROUND_COLOR = $(LOGIN_SUBMIT_ID).css("background-color");
    $(LOGIN_SUBMIT_ID).attr("disabled", true)
}

function recoverLoginBtn() {
    $(LOGIN_SUBMIT_ID).css("background-color", LOGIN_SUBMIT_BACKGROUND_COLOR);
    $(LOGIN_SUBMIT_ID).attr("disabled", false)
}

function checkForm() {
    var a = $("#cllt").val();
    if (a == "userNameLogin") {
        if (utils.requireInput($(LOGIN_USERNAME_ID), 0, 100, $("#showErrorTip"), inputUserNameTip, $(LOGIN_USERNAME_ID).parent()) || utils.requireInput($(LOGIN_PASSWORD_ID), 0, 32, $("#showErrorTip"), inputPasswordTip, $(LOGIN_PASSWORD_ID).parent())) {
            return
        }
        if (checkSpecificKey($(LOGIN_USERNAME_ID).val())) {
            return
        }
        if (needCaptcha && captchaSwitch == "1" && utils.requireInput($(LOGIN_CAPTCHA_ID), 0, 10, $("#showErrorTip"), inputCodeTip, $(LOGIN_CAPTCHA_ID).parent())) {
            return
        }
        $("#saltPassword").val(encryptPassword($(LOGIN_PASSWORD_ID).val(), $("#pwdEncryptSalt").val()));
        $(LOGIN_PASSWORD_ID).attr("disabled", "disabled")
    } else {
        if (a == "dynamicLogin") {
            if (utils.requireInput($(LOGIN_ACCOUNT_ID), 0, 100, $("#showErrorTip"), inputMobileTip, $(LOGIN_ACCOUNT_ID).parent()) || utils.requireInput($(LOGIN_DYNAMIC_ID), 0, 100, $("#showErrorTip"), inputDynamicTip, $(LOGIN_DYNAMIC_ID).parent())) {
                return
            }
            if (checkSpecificKey($(LOGIN_ACCOUNT_ID).val())) {
                return
            }
        }
    }
    return true
}

function checkNeedCaptcha() {
    var a = $(LOGIN_USERNAME_ID).val().trim();
    if (a == "") {
        return
    }
    $.ajax(contextPath + "/checkNeedCaptcha.htl", {
        data: {username: a},
        cache: false,
        dataType: "json",
        async: false,
        success: function (b) {
            if (b.isNeedActive) {
                $(".dz_zzc").show();
            }
            if (b.isNeed) {
                needCaptcha = true
            } else {
                needCaptcha = false
            }
            if (credentialsCount()) {
                if ($("#captchaDiv").css("display") != "none") {
                    return
                }
            }
            reloadCaptcha(needCaptcha)
        }
    })
}

function reloadCaptcha(a) {
    if (a && captchaSwitch == "1") {
        $("#captchaDiv").show();
        $("#captchaImg").attr("src", contextPath + "/getCaptcha.htl?" + new Date().getTime())
    } else {
        $("#captcha").val("");
        $("#captchaDiv").hide()
    }
}

function getDynamicCode() {
    if (utils.requireInput($(LOGIN_ACCOUNT_ID), 0, 100, $("#showErrorTip"), inputMobileTip, $(LOGIN_ACCOUNT_ID).parent())) {
        return
    }
    if (captchaSwitch == "1" && utils.requireInput($(LOGIN_DYNAMIC_CAPTCHA_ID), 0, 100, $("#showErrorTip"), inputCodeTip, $(LOGIN_DYNAMIC_CAPTCHA_ID).parent())) {
        return
    }
    var a = encryptPassword($(LOGIN_ACCOUNT_ID).val(), DEFAULT_SALT);
    var b = $(LOGIN_DYNAMIC_CAPTCHA_ID).val();
    $.ajax(contextPath + "/dynamicCode/getDynamicCode.htl", {
        data: {mobile: a, captcha: b},
        cache: false,
        dataType: "json",
        type: "POST",
        success: function (d) {
            var c = d.code;
            if (c == "error") {
                $(LOGIN_DYNAMIC_CAPTCHA_ID).val("");
                utils.showMsg($("#showErrorTip"), d.message);
                reloadCaptcha(true)
            } else {
                if (c == "captchaError") {
                    $(LOGIN_DYNAMIC_CAPTCHA_ID).val("");
                    utils.showMsg($("#showErrorTip"), d.message);
                    reloadCaptcha(true)
                } else {
                    if (c == "timeExpire") {
                        $(LOGIN_DYNAMIC_CAPTCHA_ID).val("");
                        if (!utils.isEmptyStr(d.time)) {
                            getTimes(d.time)
                        }
                        utils.showMsg($("#showErrorTip"), d.message)
                    } else {
                        if (c == "success") {
                            $("#showErrorTip").empty();
                            utils.showMsg($("#showWarnTip"), d.message, 0);
                            getTimes(d.intervalTime)
                        }
                    }
                }
            }
        }
    })
}

function setUrlForSuccessByClass(a) {
    var b = $(".item .combinedLoginPlugin");
    if (b) {
        b.each(function () {
            $(this).attr("href", $(this).attr("href") + "&success=" + encodeURIComponent(a))
        })
    }
    var c = $(".idsUnion_loginFont_a");
    if (c) {
        c.each(function () {
            $(this).attr("href", $(this).attr("href") + "&success=" + encodeURIComponent(a))
        })
    }
}

function getTimes(a) {
    var b = $(".getCodeText");
    if (a == 0) {
        reloadCaptcha(true);
        a = 120;
        b.text(inputDynamicGetCode);
        b.removeClass("disabled");
        $(".get-code").css({border: "1px solid #0c4af9", "pointer-events": "auto"});
        return
    } else {
        a--;
        b.text(a + "s");
        b.addClass("disabled");
        $(".get-code").css({border: "1px solid #9E9E9E", "pointer-events": "none"})
    }
    setTimeout(function () {
        getTimes(a)
    }, 1000)
}

function createSliderCaptcha() {
    $.ajax({
        url: contextPath + "/common/toSliderCaptcha.htl", type: "get", data: {}, success: function (a) {
            $("#captchaDiv").hide();
            $("#sliderCaptchaDiv").html(a)
        }
    })
}

function checkSpecificKey(a) {
    if (reg && reg != "") {
        var b = new RegExp(reg);
        if (b.test(a)) {
            $("#showErrorTip").text(excludeRegular);
            return true
        } else {
            $("#showErrorTip").text("");
            return false
        }
    }
    return false
};
