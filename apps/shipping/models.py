# Shipping has no persisted models: rate cards live in ``rates.py`` and the chosen
# courier/fee are denormalised onto the order. This module exists so Django treats
# the package as an app with a (empty) migration namespace.
