(function () {
    var feedback_button = {
        props: ['url'],
        data: null,
        methods: {}
    };

    feedback_button.data = function () {
        var data = {
            state: 'ask',
            callback_url: this.url,
        };
        return data;
    };

    feedback_button.methods.ask = function () {
        let self = this;
        self.state = 'confirm';
    };

    feedback_button.methods.confirm = function () {
        let self = this;
        self.state = 'ask';
    };

    Q.register_vue_component('feedback_button', 'components-bulma/feedback_button/feedback_button.html',
        function(template) {
            feedback_button.template = template.data;
            return feedback_button;
        });

})();
