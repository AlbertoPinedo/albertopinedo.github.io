*24-02-23*

Microsoft anunció ayer #PyRIT, un framework de automatización, para que los profesionales de la seguridad (red team principalmente) y los ingenieros de ML puedan encontrar riesgos de forma proactiva en sus sistemas de IA generativa. 
 
Los "red teams" de IA se enfrentan a tres grandes desafíos: sondear los riesgos de seguridad como aquellos relacionados con el uso responsable de la IA, lidiar con la naturaleza probabilística de los sistemas de IA generativa y adaptarse a las arquitecturas de los sistemas de IA generativa.
 
PyRIT consta de cinco grandes piezas: 

- Targets: vendrían a ser las diferentes formulaciones para acceder a un modelo. Modelos locales, remotos (vía API), HF, AOAI, o los endpoints de AML. Es decir, como PyRIT se integra con los diferentes modelos.
- Datasets: donde el analista de seguridad codifica lo que quiere que se pruebe en el sistema. Por ejemplo, un conjunto de prompts "maliciosos", plantillas dinámicas y jailbreaks conocidos que ya se incorporan en el kit.
- Un scoring engine: ofrece dos sistemas un clasificador ML de toda la vida y un endpoint LLM para autoevaluación. Además, se puede usar con Azure Content Filter directamente. 
-Capacidades para definir estrategias de ataque flexibles: con dos modalidades; 1) una primera de envío único envía una combinación de jailbreak y prompt malicioso y espera la respuesta para dar una puntuación; 2) y una segunda de multi-envío, como la primera, pero luego responde al sistema de IA en función de la puntuación obtenida.
- Memoria: lo que permite guardar las interacciones intermedias de entrada y salida, que proporciona a los usuarios la capacidad de realizar un "cold" análisis (análisis a posteriori). 

Es un proyecto de código abierto y proporcionamos también demostraciones y un path formativo para aprender a usarlo. 
 
https://lnkd.in/eCUBVBg4
Repo: https://lnkd.in/eXuH9g8d
Webminar: https://lnkd.in/e7D_ZCCQ

#PyRIT

