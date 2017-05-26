Syncrepl Client Callbacks
=========================

When a :class:`~syncrepl_client.Syncrepl` instance wants to tell you about
something, it uses a callback.

The complete list of callbacks, their parameters, and what they mean is defined
in :class:`~syncrepl_client.callbacks.BaseCallback`.
:class:`~syncrepl_client.Syncrepl` doesn't care if your object uses instance
methods, class methods, or static methods, so long as it is able to accept the
parameters provided.

In addition to :class:`~syncrepl_client.callbacks.BaseCallback`,
:class:`~syncrepl_client.callbacks.LoggingCallback` is provided as a way to log
the callbacks being received.

Both :class:`~syncrepl_client.callbacks.BaseCallback` and
:class:`~syncrepl_client.callbacks.LoggingCallback` are described below.

BaseCallback
------------

.. autoclass:: syncrepl_client.callbacks.BaseCallback

LoggingCallback
---------------

.. autoclass:: syncrepl_client.callbacks.LoggingCallback
