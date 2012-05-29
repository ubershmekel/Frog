/*

Frog Classes

- Gallery
- Piece
    - Image
    - Video
- Viewer
    -Video Controls (use other?)
- Thumbnail
- Marquee

Which UI to use?

*/

(function(global) {
    var Frog = {};
    if (typeof exports !== 'undefined') {
        if (typeof module !== 'undefined') {
            module.exports = Frog;
        }
        else {
            exports = Frog;
        }
    }
    else {
        global.Frog = Frog;
    }

    Frog.pixel = null;
    Frog.getPixel = function() {
        if (Frog.pixel === null) {
            Frog.pixel = '/static/frog/i/pixel.png';
        }

        return Frog.pixel;
    }
    Frog.util = {
        fitToRect: function(rectW, rectH, width, height) {
            var iratio = width / height;
            var wratio = rectW / rectH;
            var scale;

            if (iratio > wratio) {
                scale = rectW / width;
            }
            else {
                scale = rectH / height;
            }

            return {width: width * scale, height: height * scale};
        }
    }
    Frog.TagManager = new Class({
        initialize: function() {
            this.tags = {};
            var self = this;
            
            new Request.JSON({
                url: '/frog/tag/',
                async: false,
                onSuccess: function(res) {
                    if (res.isSuccess) {
                        res.values.each(function(tag) {
                            self.tags[tag.id] = tag.name;
                        });
                    }
                    else if (res.isError) {
                        throw res.message;
                    }
                }
            }).GET({json:true});
        },
        get: function(arg) {
            var value;
            var self = this;
            if (typeOf(arg) === 'number') {
                value = this.tags[arg];
            }
            else {
                arg = arg.toLowerCase();
                var idx = Object.values(this.tags).indexOf(arg);
                if (idx >= 0) {
                    value = Object.keys(this.tags)[idx];
                }
                else {
                    new Request.JSON({
                        url: '/frog/tag/',
                        async: false,
                        headers: {"X-CSRFToken": Cookie.read('csrftoken')},
                        onSuccess: function(res) {
                            if (res.isSuccess) {
                                value = res.value.id;
                                self.tags[value] = res.value.name;
                            }
                        }
                    }).POST({name: arg});
                }
            }
            
            return value;
        },
        getByName: function(name) {

        },
        getByID: function(id) {

        }
    });
    Frog.Tag = new Class({
        Implements: Events,
        initialize: function(id, name) {
            var self = this;
            this.id = id;
            this.name = name || Frog.Tags.get(id);
            this.element = new Element('li', {'class': 'frog-tag'});
            this.element.dataset.frog_tag_id = this.id;
            new Element('span').inject(this.element)
            new Element('a', {href: 'javascript:void(0);', text: this.name.capitalize(), 'class': 'frog-tag'}).inject(this.element);
            this.closeButton = new Element('div', {
                text: 'x',
                events: {
                    'click': function(e) {
                        self.fireEvent('onClose', [self]);
                    }
                }
            }).inject(this.element);
        },
        toElement: function() {
            return this.element;
        }
    })
    Frog.Tags = new Frog.TagManager();

    Frog.CommentManager = new Class({
        Implements: Events,
        initialize: function() {
            Ext.require(['*']);
            var self = this;
            this.container = new Element('div', {
                id: 'frog_comments_container',
                events: {
                    click: function(e) {
                        if (e.target === this) {
                            self.close();
                        }
                    }
                }
            }).inject(document.body);
            this.element = new Element('div', {id: 'frog_comments_block'}).inject(this.container);
            this.container.hide();
            this.saveButton = null;
            this.guid = '';
            this.request = new Request.HTML({
                url: '/frog/comment/',
                evalScripts: true,
                noCache: true,
                onSuccess: function(tree, elements, html) {
                    this.open(html);
                }.bind(this)
            });
            this.top = new Element('div').inject(this.element);
            var bot = new Element('div').inject(this.element);
            this.fakeInput = new Element('input', {
                'placeholder': 'Comment...',
                events: {
                    click: function(e) {
                        e.stop();
                        this.hide();
                        var el = $('frog_comments');
                        var guid = el.dataset.frog_guid;
                        var id = el.dataset.frog_gallery_id;
                        self.input.show();
                        self.input.focus();
                        if (!self.saveButton) {
                            self.saveButton = Ext.create('Ext.Button', {
                                text: 'Save',
                                renderTo: bot,
                                handler: function() {
                                    new Request.JSON({
                                        url: '/frog/comment/'
                                    }).POST({guid: guid, comment: self.input.value});
                                    self.close();

                                    self.fireEvent('onPost', [id]);
                                }
                            });
                            Ext.create('Ext.Button', {
                                text: 'Cancel',
                                renderTo: bot,
                                handler: function() {
                                    self.close();
                                }
                            })
                        }
                    }
                }
            }).inject(bot);
            this.input = new Element('textarea').inject(bot);
            this.input.hide();
            this.scrollEvent = function(e) {
                e.stop();
            }
        },
        get: function(guid, id) {
            this.guid = guid;
            this.request.GET({guid: guid, id: id});
        },
        open: function(html) {
            this.container.show();
            var expression = /[-a-zA-Z0-9@:%_\+.~#?&//=]{2,256}\.[a-z]{2,4}\b(\/[-a-zA-Z0-9@:%_\+.~#?&//=]*)?/gi;
            var regex = new RegExp(expression);
            var matches = html.match(regex);
            if (matches) {
                for (var i=0;i<matches.length;i++) {
                    var link = matches[i];
                    var a = '<a href="' + link + '" target="_blank">' + link + '</a>';
                    html = html.replace(link, a);
                }
            }
            this.top.set('html', html);
            window.addEvent('mousewheel', this.scrollEvent);
        },
        close: function() {
            this.container.hide();
            this.fakeInput.show();
            this.input.value = "";
            this.input.hide();
            window.removeEvent('mousewheel', this.scrollEvent);
        }
    });
    Frog.Comments = new Frog.CommentManager();

})(window);