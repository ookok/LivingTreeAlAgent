
/****************************************************************************
**
** Copyright (C) 2016 The Qt Company Ltd.
** Contact: https://www.qt.io/licensing/
**
** This file is part of the QtWebChannel module of the Qt Toolkit.
**
** $QT_BEGIN_LICENSE:BSD$
** Commercial License Usage
** Licensees holding valid commercial Qt licenses may use this file in
** accordance with the commercial license agreement provided with the
** Software or, alternatively, in accordance with the terms contained in
** a written agreement between you and The Qt Company. For licensing terms
** and conditions see https://www.qt.io/terms-conditions. For further
** information use the contact form at https://www.qt.io/contact-us.
**
** BSD License Usage
** Alternatively, you may use this file under the terms of the BSD license
** as follows:
**
** "Redistribution and use in source and binary forms, with or without
** modification, are permitted provided that the following conditions are
** met:
**   * Redistributions of source code must retain the above copyright
**     notice, this list of conditions and the following disclaimer.
**   * Redistributions in binary form must reproduce the above copyright
**     notice, this list of conditions and the following disclaimer in
**     the documentation and/or other materials provided with the
**     distribution.
**   * Neither the name of The Qt Company Ltd nor the names of its
**     contributors may be used to endorse or promote products derived
**     from this software without specific prior written permission.
**
**
** THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
** "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
** LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
** A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
** OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
** SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
** LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
** DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
** THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
** (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
** OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE."
**
** $QT_END_LICENSE$
**
****************************************************************************/

"use strict";

var QWebChannelMessageTypes = {
    signal: 1,
    propertyUpdate: 2,
    init: 3,
    idle: 4,
    debug: 5,
    invokeMethod: 6,
    connectToSignal: 7,
    disconnectFromSignal: 8,
    setProperty: 9,
    response: 10
};

var QWebChannel = function(transport, initCallback) {
    if (typeof transport !== "object" || typeof transport.send !== "function") {
        console.error("The QWebChannel expects a transport object with a send function.");
        return;
    }

    var self = this;
    this.transport = transport;
    this.execCallbacks = {};
    this.execId = 0;

    this.objects = {};

    function send(data) {
        transport.send(JSON.stringify(data));
    }

    function exec(data, callback) {
        if (callback) {
            self.execId++;
            data.id = self.execId;
            self.execCallbacks[self.execId] = callback;
        }
        send(data);
    }

    this.exec = exec;

    transport.onmessage = function(message) {
        var data = JSON.parse(message.data);
        switch (data.type) {
            case QWebChannelMessageTypes.signal:
                if (data.object in self.objects && data.signal in self.objects[data.object].signals) {
                    self.objects[data.object].signals[data.signal].emit(data.args);
                }
                break;
            case QWebChannelMessageTypes.response:
                if (data.id in self.execCallbacks) {
                    var callback = self.execCallbacks[data.id];
                    delete self.execCallbacks[data.id];
                    callback(data.data);
                }
                break;
            case QWebChannelMessageTypes.init:
                for (var objectName in data.objects) {
                    var objectData = data.objects[objectName];
                    self.objects[objectName] = new QObject(objectName, self, objectData);
                }
                if (initCallback) {
                    initCallback(self);
                }
                break;
            default:
                console.error("Unknown message type: " + data.type, data);
        }
    };

    function QObject(name, webChannel, data) {
        this.__id__ = name;
        this.__webChannel__ = webChannel;

        var signals = data.signals || [];
        var methods = data.methods || [];
        var properties = data.properties || [];
        var enums = data.enums || [];

        this.signals = {};
        this.enums = {};

        var self = this;

        function unwrap(QObjectList) {
            var result = [];
            for (var i = 0; i < QObjectList.length; i++) {
                var qObject = QObjectList[i];
                result.push(qObject.__qtObject__);
            }
            return result;
        }

        function wrapQObject(qObject) {
            return {
                "__qtObject__": qObject,
                "__id__": qObject.__id__,
                "__webChannel__": self.__webChannel__
            };
        }

        for (var i = 0; i < signals.length; ++i) {
            var signal = signals[i];
            (function(signal) {
                self[signal] = function() {
                    self.signals[signal].emit.apply(self.signals[signal], arguments);
                };
                self[signal].connect = function(callback) {
                    self.__webChannel__.exec({
                        type: QWebChannelMessageTypes.connectToSignal,
                        object: self.__id__,
                        signal: signal
                    }, function(response) {
                        self.signals[signal].connect(callback);
                    });
                };
                self[signal].disconnect = function(callback) {
                    self.__webChannel__.exec({
                        type: QWebChannelMessageTypes.disconnectFromSignal,
                        object: self.__id__,
                        signal: signal
                    }, function(response) {
                        self.signals[signal].disconnect(callback);
                    });
                };
                self[signal].disconnectAll = function() {
                    self.signals[signal].disconnectAll();
                };
            })(signal);
        }

        for (var i = 0; i < methods.length; ++i) {
            var method = methods[i];
            (function(method) {
                self[method] = function() {
                    var args = Array.prototype.slice.call(arguments);
                    var callback;
                    if (args.length && typeof args[args.length - 1] === "function") {
                        callback = args.pop();
                    }
                    self.__webChannel__.exec({
                        type: QWebChannelMessageTypes.invokeMethod,
                        object: self.__id__,
                        method: method,
                        args: args
                    }, callback);
                };
            })(method);
        }

        for (var i = 0; i < properties.length; ++i) {
            var property = properties[i];
            this[property.name] = property.value;
            (function(propertyName) {
                self["__get__" + propertyName] = function() {
                    return self[propertyName];
                };
                self["__set__" + propertyName] = function(value) {
                    self.__webChannel__.exec({
                        type: QWebChannelMessageTypes.setProperty,
                        object: self.__id__,
                        property: propertyName,
                        value: value
                    }, function(response) {
                        self[propertyName] = response;
                    });
                };
            })(property.name);
        }

        for (var i = 0; i < enums.length; ++i) {
            var enumDef = enums[i];
            var enumName = enumDef.name;
            this.enums[enumName] = enumDef.values;
            (function(enumDef) {
                self[enumDef.name] = enumDef.values;
            })(enumDef);
        }

        for (var i = 0; i < signals.length; ++i) {
            var signalName = signals[i];
            this.signals[signalName] = new QSignal(signalName, this);
        }
    }

    function QSignal(name, parentObject) {
        this.name = name;
        this.object = parentObject;
        this.connections = [];
    }

    QSignal.prototype.connect = function(callback) {
        this.connections.push(callback);
    };

    QSignal.prototype.disconnect = function(callback) {
        if (!callback) {
            this.disconnectAll();
        } else {
            var index = this.connections.indexOf(callback);
            if (index !== -1) {
                this.connections.splice(index, 1);
            }
        }
    };

    QSignal.prototype.disconnectAll = function() {
        this.connections = [];
    };

    QSignal.prototype.emit = function() {
        var args = Array.prototype.slice.call(arguments);
        for (var i = 0; i < this.connections.length; ++i) {
            this.connections[i].apply(this, args);
        }
    };

    send({
        type: QWebChannelMessageTypes.init
    });
};
