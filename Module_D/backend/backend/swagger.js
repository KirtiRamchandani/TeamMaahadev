const swaggerJsdoc = require('swagger-jsdoc');

const options = {
  definition: {
    openapi: '3.0.0',
    info: {
      title: 'API Endpoints',
      version: '1.0.0',
      description: 'A short description of the API endpoints used by Team India',
    },
  },
  apis: ['./src/*.js']
};

const swaggerSpec = swaggerJsdoc(options);
module.exports = swaggerSpec;